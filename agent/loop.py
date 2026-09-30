import json

from openai import OpenAI
from openai.types.responses import (
    FunctionToolParam,
    ResponseFunctionToolCall,
    ResponseInputParam,
    ResponseOutputMessage,
    ResponseOutputRefusal,
    ResponseOutputText,
    ResponseReasoningItem,
)

from agent.executor import TOOLS, execute_action
from agent.state import Action, LoopState, State, TextTurn, ToolCallTurn, ToolName
from config.settings import BudgetSettings, LoopSettings, ToolSettings
from router.azure_client import to_azure_tool_definition


def check_stop_conditions(
    state: State, loop: LoopSettings, budget: BudgetSettings
) -> LoopState | None:
    last_turn = state.conversation[-1] if state.conversation else None
    match last_turn:
        case None:
            pass  # nothing has happened yet; nothing to stop for
        case ToolCallTurn(action=Action(tool=ToolName.SUBMIT)):
            return LoopState.SUBMIT_CALLED
        case ToolCallTurn():
            pass  # a real tool call; the checks below still apply
        case TextTurn():
            return LoopState.MODEL_REPLIED_WITHOUT_TOOL

    # match/case is a statement, not an expression, so a list comprehension
    # still needs isinstance here rather than a case pattern.
    tool_call_turns = [
        turn for turn in state.conversation if isinstance(turn, ToolCallTurn)
    ]

    if len(tool_call_turns) >= loop.max_steps:
        return LoopState.STEP_LIMIT_HIT

    if state.token_count >= budget.max_tokens:
        return LoopState.TOKEN_BUDGET_HIT

    if state.spend >= budget.max_spend:
        return LoopState.COST_CEILING_HIT

    if len(tool_call_turns) >= loop.last_action_repeat_limit:
        last_actions = [
            turn.action for turn in tool_call_turns[-loop.last_action_repeat_limit :]
        ]
        if all(action == last_actions[0] for action in last_actions):
            return LoopState.REPEATED_ACTION

    return None


def call_model(client: OpenAI, model: str, state: State) -> Action | str:
    tools: list[FunctionToolParam] = [
        to_azure_tool_definition(tool_specification)
        for tool_specification, _ in TOOLS.values()
    ]
    input_items: ResponseInputParam = [{"role": "user", "content": state.task}]

    for turn in state.conversation:
        match turn:
            case TextTurn(text=text):
                input_items.append({"role": "assistant", "content": text})
            case ToolCallTurn(action=action, observation=observation):
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

    # response.output can include items we don't act on (e.g. a reasoning
    # item from a reasoning model), so scan for the first item that is
    # actually a tool call or a message, rather than assuming index 0.
    for call in response.output:
        match call:
            case ResponseFunctionToolCall():
                arguments = json.loads(call.arguments)
                return Action(
                    tool=ToolName(call.name), call_id=call.call_id, arguments=arguments
                )
            case ResponseOutputMessage():
                match call.content[0]:
                    case ResponseOutputText():
                        return call.content[0].text
                    case ResponseOutputRefusal():
                        return call.content[0].refusal
                    case _:
                        raise ValueError(
                            f"Unexpected message content type: {type(call.content[0])}"
                        )
            case ResponseReasoningItem():
                continue  # not actionable; keep looking
            case _:
                continue  # unrecognized item type; keep looking

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

        result = call_model(client, model, state)

        match result:
            case Action():
                observation = execute_action(result, tool_settings)
                state.conversation.append(
                    ToolCallTurn(action=result, observation=observation)
                )
            case str():
                state.conversation.append(TextTurn(text=result))

        # Update token count and spend (fake values for now)
        state.token_count += 10  # fake increment
        state.spend += 0.01  # fake increment

    return state
