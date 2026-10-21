from agent.loop import check_stop_conditions
from agent.state import (
    Action,
    InvalidToolCall,
    LoopState,
    MessagePhase,
    State,
    TextTurn,
    ToolCallTurn,
    ToolName,
    UserTurn,
)
from config.settings import BudgetSettings, LoopSettings

# small limits so each test needs only a few turns
LOOP = LoopSettings(
    max_steps=10, last_action_repeat_limit=3, max_consecutive_invalid_calls=2
)
BUDGET = BudgetSettings(max_tokens=1_000, max_spend=1.00)


# builders: one line per turn in each test instead of nested constructors
def read_call(file_path: str = "app.py", call_id: str = "call") -> ToolCallTurn:
    action = Action(
        tool=ToolName.READ, call_id=call_id, arguments={"file_path": file_path}
    )
    return ToolCallTurn(action=action, observation="ok")


def invalid_call() -> ToolCallTurn:
    action = InvalidToolCall(name="nope", call_id="call", arguments="{}")
    return ToolCallTurn(action=action, observation="error")


def stop_reason(*turns, token_count: int = 0, spend: float = 0.0) -> LoopState | None:
    state = State(conversation=list(turns), token_count=token_count, spend=spend)
    return check_stop_conditions(state, LOOP, BUDGET)


def test_empty_conversation_keeps_going():
    assert stop_reason() is None


def test_final_answer_stops():
    turns = [UserTurn("fix it"), TextTurn("done", phase=MessagePhase.FINAL_ANSWER)]
    assert stop_reason(*turns) is LoopState.FINAL_ANSWER_GIVEN


def test_commentary_keeps_going():
    turns = [UserTurn("fix it"), TextTurn("looking", phase=MessagePhase.COMMENTARY)]
    assert stop_reason(*turns) is None


def test_step_limit_stops():
    turns = [UserTurn("fix it")] + [read_call(f"f{i}.py") for i in range(10)]
    assert stop_reason(*turns) is LoopState.STEP_LIMIT_HIT


def test_step_limit_counts_only_the_current_prompt():
    earlier = [UserTurn("first")] + [read_call(f"a{i}.py") for i in range(9)]
    current = [UserTurn("second")] + [read_call(f"b{i}.py") for i in range(9)]
    assert stop_reason(*earlier, *current) is None


def test_token_budget_stops():
    assert (
        stop_reason(UserTurn("fix it"), token_count=1_000) is LoopState.TOKEN_BUDGET_HIT
    )


def test_cost_ceiling_stops():
    assert stop_reason(UserTurn("fix it"), spend=1.00) is LoopState.COST_CEILING_HIT


def test_same_call_three_times_stops():
    # call ids differ on every real call, so they must not hide a repeat
    turns = [UserTurn("fix it")] + [read_call(call_id=f"c{i}") for i in range(3)]
    assert stop_reason(*turns) is LoopState.REPEATED_ACTION


def test_same_tool_with_different_arguments_keeps_going():
    turns = [UserTurn("fix it")] + [read_call(f"f{i}.py") for i in range(3)]
    assert stop_reason(*turns) is None


def test_invalid_calls_in_a_row_stop():
    turns = [UserTurn("fix it"), invalid_call(), invalid_call()]
    assert stop_reason(*turns) is LoopState.INVALID_CALL_LIMIT_HIT


def test_valid_call_resets_invalid_count():
    turns = [UserTurn("fix it"), invalid_call(), read_call(), invalid_call()]
    assert stop_reason(*turns) is None
