import json

from openai import OpenAI
from openai.types.responses import (
    EasyInputMessageParam,
    FunctionToolParam,
    ResponseFunctionToolCall,
    ResponseInputParam,
    ResponseOutputMessage,
    ResponseOutputRefusal,
    ResponseOutputText,
    ResponseReasoningItem,
)

from agent.executor import TOOLS, execute_action
from agent.state import (
    Action,
    LoopState,
    Message,
    MessagePhase,
    Reasoning,
    State,
    TextTurn,
    ToolCallTurn,
    ToolName,
)
from config.settings import BudgetSettings, LoopSettings, ToolSettings
from router.azure_client import to_azure_tool_definition


def check_stop_conditions(
    state: State, loop: LoopSettings, budget: BudgetSettings
) -> LoopState | None:
    last_turn = state.conversation[-1] if state.conversation else None
    match last_turn:
        case None:
            pass  # nothing has happened yet; nothing to stop for
        case ToolCallTurn():
            pass  # a real tool call; the checks below still apply
        case TextTurn(phase=MessagePhase.FINAL_ANSWER):
            return LoopState.MODEL_REPLIED_WITHOUT_TOOL
        case TextTurn():
            pass  # commentary or no phase: the model isn't done; keep going

    tool_call_turns = [
        turn for turn in state.conversation if isinstance(turn, ToolCallTurn)
    ]

    # every model call counts as a step, text replies included
    if len(state.conversation) >= loop.max_steps:
        return LoopState.STEP_LIMIT_HIT

    if state.token_count >= budget.max_tokens:
        return LoopState.TOKEN_BUDGET_HIT

    if state.spend >= budget.max_spend:
        return LoopState.COST_CEILING_HIT

    if len(tool_call_turns) >= loop.last_action_repeat_limit:
        last_actions = [
            turn.action for turn in tool_call_turns[-loop.last_action_repeat_limit :]
        ]
        first = last_actions[0]
        # call_id is new on every call, so compare only what the call does
        if all(
            (action.tool, action.arguments) == (first.tool, first.arguments)
            for action in last_actions
        ):
            return LoopState.REPEATED_ACTION

    return None


def to_assistant_input(message: Message) -> EasyInputMessageParam:
    item: EasyInputMessageParam = {"role": "assistant", "content": message.text}
    # phase is optional; only send it back when the model gave one
    if message.phase is not None:
        item["phase"] = message.phase.value
    return item


def call_model(
    client: OpenAI, model: str, state: State
) -> tuple[Action | Message, Reasoning | None, Message | None]:
    tools: list[FunctionToolParam] = [
        to_azure_tool_definition(tool_specification)
        for tool_specification, _ in TOOLS.values()
    ]
    input_items: ResponseInputParam = [{"role": "user", "content": state.task}]

    for turn in state.conversation:
        if turn.reasoning is not None:
            input_items.append({  # type: ignore[arg-type]
                "type": "reasoning",
                **turn.reasoning.__dict__,
            })
            
        match turn:
            case TextTurn(text=text, phase=phase):
                input_items.append(to_assistant_input(Message(text=text, phase=phase)))
            case ToolCallTurn(action=action, observation=observation, preamble=preamble):
                if preamble is not None:
                    input_items.append(to_assistant_input(preamble))
                input_items.append(
                    {
                        "type": "function_call",
                        "call_id": action.call_id,
                        "name": action.tool.value,
                        "arguments": json.dumps(action.arguments),
                    }
                )
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": action.call_id,
                        "output": observation,
                    }
                )

    response = client.responses.create(
        model=model,
        instructions="You are a coding agent. Use the tools to solve the task.",
        input=input_items,
        tools=tools,
        parallel_tool_calls=False,
    )

    # response.output can hold several items in one response: a reasoning
    # item, a message, and a function call can all come back together
    # (e.g. [reasoning, message(phase=commentary), function_call]). So scan
    # every item instead of stopping at the first one. If there is a
    # function call, it is the action and any message is its preamble; a
    # message is only the model's reply when no function call came with it.
    reasoning: Reasoning | None = None
    message: Message | None = None
    action: Action | None = None
    for call in response.output:
        match call:
            case ResponseFunctionToolCall():
                arguments = json.loads(call.arguments)
                action = Action(
                    tool=ToolName(call.name), call_id=call.call_id, arguments=arguments
                )
            case ResponseOutputMessage():
                phase = MessagePhase(call.phase) if call.phase is not None else None
                match call.content[0]:
                    case ResponseOutputText():
                        message = Message(text=call.content[0].text, phase=phase)
                    case ResponseOutputRefusal():
                        message = Message(text=call.content[0].refusal, phase=phase)
                    case _:
                        raise ValueError(
                            f"Unexpected message content type: {type(call.content[0])}"
                        )
            case ResponseReasoningItem():
                reasoning = Reasoning(
                    id=call.id,
                    summary=[s.text for s in call.summary],
                    content=[c.text for c in (call.content or [])],
                    encrypted_content=call.encrypted_content,
                )
                continue  # not actionable; keep looking
            case _:
                continue  # unrecognized item type; keep looking

    if action is not None:
        return action, reasoning, message
    if message is not None:
        return message, reasoning, None
    raise ValueError(
        f"No function call or message found in response output: {[item.type for item in response.output]}"
    )


def run_agent_loop(
    client: OpenAI,
    model: str,
    state: State,
    loop: LoopSettings,
    budget: BudgetSettings,
    tool_settings: ToolSettings,
) -> State:
    while True:
        stop_reason = check_stop_conditions(state, loop, budget)
        if stop_reason is not None:
            state.stop_reason = stop_reason
            break

        result, reasoning, preamble = call_model(client, model, state)

        match result:
            case Action():
                observation = execute_action(result, tool_settings)
                state.conversation.append(
                    ToolCallTurn(
                        action=result,
                        observation=observation,
                        reasoning=reasoning,
                        preamble=preamble,
                    )
                )
            case Message(text=text, phase=phase):
                state.conversation.append(
                    TextTurn(text=text, phase=phase, reasoning=reasoning)
                )

        # Update token count and spend (fake values for now)
        state.token_count += 10  # fake increment
        state.spend += 0.01  # fake increment

    return state
