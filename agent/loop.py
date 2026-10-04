import json

from openai import APIError, OpenAI
from openai.types.responses import (
    EasyInputMessageParam,
    FunctionToolParam,
    Response,
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
    InvalidToolCall,
    LoopState,
    Message,
    MessagePhase,
    Reasoning,
    State,
    TextTurn,
    ToolCallTurn,
    ToolName,
)
from config.settings import (
    BudgetSettings,
    LoopSettings,
    PricingSettings,
    ProtectedPathSettings,
    ToolSettings,
    WorkSpaceSettings,
)
from hooks.policy import Policy
from router.azure_client import to_azure_tool_definition
from router.pricing import compute_cost


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
            return LoopState.FINAL_ANSWER_GIVEN
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

    # count invalid calls in a row at the end; a real tool call resets it
    invalid_calls_in_a_row = 0
    for turn in reversed(tool_call_turns):
        if not isinstance(turn.action, InvalidToolCall):
            break
        invalid_calls_in_a_row += 1
    if invalid_calls_in_a_row >= loop.max_consecutive_invalid_calls:
        return LoopState.INVALID_CALL_LIMIT_HIT

    # only real actions count as repeats; invalid calls are capped above
    actions = [
        turn.action for turn in tool_call_turns if isinstance(turn.action, Action)
    ]
    if len(actions) >= loop.last_action_repeat_limit:
        last_actions = actions[-loop.last_action_repeat_limit :]
        first = last_actions[0]
        # call_id is new on every call, so compare only what the call does
        if all(
            (action.tool, action.arguments) == (first.tool, first.arguments)
            for action in last_actions
        ):
            return LoopState.REPEATED_ACTION

    return None


def build_input(state: State) -> ResponseInputParam:
    input_items: ResponseInputParam = [{"role": "user", "content": state.task}]

    for turn in state.conversation:
        if turn.reasoning is not None:
            input_items.append(
                {
                    "type": "reasoning",
                    "id": turn.reasoning.id,
                    "summary": [
                        {"type": "summary_text", "text": text}
                        for text in turn.reasoning.summary
                    ],
                    "content": [
                        {"type": "reasoning_text", "text": text}
                        for text in turn.reasoning.content
                    ],
                    "encrypted_content": turn.reasoning.encrypted_content,
                }
            )

        match turn:
            case TextTurn(text=text, phase=phase):
                input_items.append(to_assistant_input(Message(text=text, phase=phase)))
            case ToolCallTurn(
                action=action, observation=observation, preamble=preamble
            ):
                if preamble is not None:
                    input_items.append(to_assistant_input(preamble))
                # replay exactly what the model sent, even when it was invalid
                match action:
                    case Action(tool=tool, arguments=parsed_arguments):
                        name = tool.value
                        arguments = json.dumps(parsed_arguments)
                    case InvalidToolCall(name=raw_name, arguments=raw_arguments):
                        name = raw_name
                        arguments = raw_arguments
                input_items.append(
                    {
                        "type": "function_call",
                        "call_id": action.call_id,
                        "name": name,
                        "arguments": arguments,
                    }
                )
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": action.call_id,
                        "output": observation,
                    }
                )

    return input_items


def to_assistant_input(message: Message) -> EasyInputMessageParam:
    item: EasyInputMessageParam = {"role": "assistant", "content": message.text}
    # phase is optional; only send it back when the model gave one
    if message.phase is not None:
        item["phase"] = message.phase.value
    return item


def call_model(client: OpenAI, model: str, state: State) -> Response:
    tools: list[FunctionToolParam] = [
        to_azure_tool_definition(tool_specification)
        for tool_specification, _ in TOOLS.values()
    ]
    input_items = build_input(state)

    response = client.responses.create(
        model=model,
        instructions="You are a coding agent. Use the tools to solve the task.",
        input=input_items,
        tools=tools,
        parallel_tool_calls=False,
    )
    return response


def to_action(call: ResponseFunctionToolCall) -> Action | InvalidToolCall:
    # keep exactly what the model sent if it can't become a real Action
    invalid = InvalidToolCall(
        name=call.name, call_id=call.call_id, arguments=call.arguments
    )
    try:
        tool = ToolName(call.name)
        arguments = json.loads(call.arguments)
    except ValueError:  # unknown tool name, or broken JSON
        return invalid
    # a tool that isn't built yet, or valid JSON that isn't an object
    if tool not in TOOLS or not isinstance(arguments, dict):
        return invalid
    return Action(tool=tool, call_id=call.call_id, arguments=arguments)


def parse_response(
    response: Response,
) -> tuple[Action | InvalidToolCall | Message, Reasoning | None, Message | None]:
    # response.output can hold several items in one response: a reasoning
    # item, a message, and a function call can all come back together
    # (e.g. [reasoning, message(phase=commentary), function_call]). So scan
    # every item instead of stopping at the first one. If there is a
    # function call, it is the action and any message is its preamble; a
    # message is only the model's reply when no function call came with it.
    reasoning: Reasoning | None = None
    message: Message | None = None
    action: Action | InvalidToolCall | None = None
    for item in response.output:
        match item:
            case ResponseFunctionToolCall():
                action = to_action(item)
            case ResponseOutputMessage():
                phase = MessagePhase(item.phase) if item.phase is not None else None
                match item.content[0]:
                    case ResponseOutputText():
                        message = Message(text=item.content[0].text, phase=phase)
                    case ResponseOutputRefusal():
                        message = Message(text=item.content[0].refusal, phase=phase)
                    case _:
                        raise ValueError(
                            f"Unexpected message content type: {type(item.content[0])}"
                        )
            case ResponseReasoningItem():
                reasoning = Reasoning(
                    id=item.id,
                    summary=[s.text for s in item.summary],
                    content=[c.text for c in (item.content or [])],
                    encrypted_content=item.encrypted_content,
                )
            case _:
                pass  # an item type we don't act on

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
    workspace_settings: WorkSpaceSettings,
    pricing: PricingSettings,
    policy: Policy,
    protected_settings: ProtectedPathSettings,
) -> State:
    while True:
        stop_reason = check_stop_conditions(state, loop, budget)
        if stop_reason is not None:
            state.stop_reason = stop_reason
            break

        try:
            response = call_model(client, model, state)
        except APIError:
            state.stop_reason = LoopState.API_ERROR
            break

        # count what this call used before anything else can fail
        if response.usage is not None:
            state.token_count += response.usage.total_tokens
            state.spend += compute_cost(response.usage, pricing)

        result, reasoning, preamble = parse_response(response)

        match result:
            case Action() | InvalidToolCall():
                observation = execute_action(
                    result,
                    tool_settings,
                    root_path=workspace_settings.root_path,
                    policy=policy,
                    protected_settings=protected_settings,
                )
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

    return state
