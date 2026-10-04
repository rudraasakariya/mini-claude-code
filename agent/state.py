from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LoopState(Enum):
    STEP_LIMIT_HIT = "step_limit_hit"
    TOKEN_BUDGET_HIT = "token_budget_hit"
    COST_CEILING_HIT = "cost_ceiling_hit"
    REPEATED_ACTION = "repeated_action"
    INVALID_CALL_LIMIT_HIT = "invalid_call_limit_hit"
    FINAL_ANSWER_GIVEN = "final_answer_given"
    API_ERROR = "api_error"


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


class MessagePhase(Enum):
    COMMENTARY = "commentary"
    FINAL_ANSWER = "final_answer"


@dataclass
class Message:
    text: str
    phase: MessagePhase | None = None


@dataclass
class Reasoning:
    id: str
    summary: list[str] = field(default_factory=list)
    content: list[str] = field(default_factory=list)
    encrypted_content: str | None = None


@dataclass
class Action:
    tool: ToolName
    call_id: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class InvalidToolCall:
    name: str
    call_id: str
    arguments: str


@dataclass
class ToolCallTurn:
    action: Action | InvalidToolCall
    observation: str
    reasoning: Reasoning | None = None
    preamble: Message | None = None


@dataclass
class TextTurn:
    text: str
    phase: MessagePhase | None = None
    reasoning: Reasoning | None = None


Turn = ToolCallTurn | TextTurn


@dataclass
class State:
    task: str
    conversation: list[Turn] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    token_count: int = 0
    spend: float = 0.0
    stop_reason: LoopState | None = None
