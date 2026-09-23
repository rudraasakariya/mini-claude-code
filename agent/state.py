from dataclasses import dataclass , field
from typing import Any
from enum import Enum

class LoopState(Enum):
    SUBMIT_CALLED = "submit_called"
    STEP_LIMIT_HIT = "step_limit_hit"
    TOKEN_BUDGET_HIT = "token_budget_hit"
    COST_CEILING_HIT = "cost_ceiling_hit"
    REPEATED_ACTION = "repeated_action"

class ToolName(Enum):
    GREP = "grep"
    GLOB = "glob"
    READ = "read"
    EDIT = "edit"
    RUN = "run"
    FIND_DEFINITION = "find_definition"
    FIND_CALLERS = "find_callers"
    FIND_TESTS_FOR = "find_tests_for"
    PATH_BETWEEN = "path_between"
    SUBMIT = "submit"

@dataclass
class Action:
    tool: ToolName
    arguments: dict[str, Any] = field(default_factory=dict)

@dataclass
class Step:
    action: Action
    observation: str

@dataclass
class State:
    task: str
    steps: list[Step] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    token_count: int = 0
    spend: float = 0.0
    stop_reason: LoopState | None = None