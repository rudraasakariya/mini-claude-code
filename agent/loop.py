import json
import time

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

from agent.events import (
    AssistantText,
    EventHandler,
    ModelCallStarted,
    RunFinished,
    StepFinished,
    StepUsage,
    ToolCallFinished,
    ToolCallStarted,
    ignore_event,
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
    Turn,
    UserTurn,
)
from config.settings import BudgetSettings, LoopSettings, RunConfig
from hooks.guardrails import Guardrails
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
        case UserTurn():
            pass  # user input doesn't stop the loop; keep going

    # step, repeat and invalid-call checks only look at the current prompt's
    # turns, i.e. everything after the user's last message
    turns_this_prompt: list[Turn] = []
    for turn in reversed(state.conversation):
        if isinstance(turn, UserTurn):
            break
        turns_this_prompt.append(turn)
    turns_this_prompt.reverse()

    tool_call_turns = [
        turn for turn in turns_this_prompt if isinstance(turn, ToolCallTurn)
    ]

    # every model call counts as a step, text replies included
    if len(turns_this_prompt) >= loop.max_steps:
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
    input_items: ResponseInputParam = []

    for turn in state.conversation:
        if isinstance(turn, UserTurn):
            input_items.append({"role": "user", "content": turn.prompt})
            continue
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
    config: RunConfig,
    guardrails: Guardrails,
    on_event: EventHandler = ignore_event,
) -> State:
    state.stop_reason = None  # a new prompt starts a new run
    while True:
        stop_reason = check_stop_conditions(state, config.loop, config.budget)
        if stop_reason is not None:
            state.stop_reason = stop_reason
            break

        on_event(ModelCallStarted())
        started = time.perf_counter()
        try:
            response = call_model(client, model, state)
        except APIError:
            state.stop_reason = LoopState.API_ERROR
            break
        latency_seconds = time.perf_counter() - started

        # count what this call used before anything else can fail
        usage = StepUsage()
        if response.usage is not None:
            usage = StepUsage(
                input_tokens=response.usage.input_tokens,
                cached_tokens=response.usage.input_tokens_details.cached_tokens,
                output_tokens=response.usage.output_tokens,
                cost=compute_cost(response.usage, config.pricing),
            )
            state.token_count += response.usage.total_tokens
            state.spend += usage.cost

        result, reasoning, preamble = parse_response(response)

        match result:
            case Action() | InvalidToolCall():
                on_event(ToolCallStarted(action=result, preamble=preamble))
                execution = execute_action(
                    result,
                    config.tools,
                    root_path=config.workspace.root_path,
                    guardrails=guardrails,
                    protected_settings=config.protected_paths,
                )
                on_event(
                    ToolCallFinished(action=result, observation=execution.observation)
                )
                turn = ToolCallTurn(
                    action=result,
                    observation=execution.observation,
                    reasoning=reasoning,
                    preamble=preamble,
                )
                blocked_rule = execution.blocked_rule
            case Message(text=text, phase=phase):
                on_event(AssistantText(message=result))
                turn = TextTurn(text=text, phase=phase, reasoning=reasoning)
                blocked_rule = None

        state.conversation.append(turn)
        on_event(
            StepFinished(
                turn=turn,
                usage=usage,
                latency_seconds=latency_seconds,
                blocked_rule=blocked_rule,
            )
        )

    if state.stop_reason is not None:
        on_event(
            RunFinished(
                stop_reason=state.stop_reason,
                token_count=state.token_count,
                spend=state.spend,
            )
        )
    return state
