from collections.abc import Callable
from dataclasses import dataclass

from agent.state import (
    Action,
    InvalidToolCall,
    LoopState,
    Message,
    TextTurn,
    ToolCallTurn,
)


@dataclass(frozen=True)
class ModelCallStarted:
    """The loop is waiting for the model's next reply."""


@dataclass(frozen=True)
class ToolCallStarted:
    action: Action | InvalidToolCall
    preamble: Message | None


@dataclass(frozen=True)
class ToolCallFinished:
    action: Action | InvalidToolCall
    observation: str


@dataclass(frozen=True)
class AssistantText:
    message: Message


@dataclass(frozen=True)
class StepUsage:
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0


@dataclass(frozen=True)
class StepFinished:
    """One model call and what came of it: everything the trace needs."""

    turn: ToolCallTurn | TextTurn
    usage: StepUsage
    latency_seconds: float
    blocked_rule: str | None = None


@dataclass(frozen=True)
class RunFinished:
    stop_reason: LoopState
    token_count: int
    spend: float


AgentEvent = (
    ModelCallStarted
    | ToolCallStarted
    | ToolCallFinished
    | AssistantText
    | StepFinished
    | RunFinished
)

# whoever shows the run (CLI, TUI, tests) passes one of these to the loop
EventHandler = Callable[[AgentEvent], None]


def ignore_event(event: AgentEvent) -> None:
    """Default handler for callers that don't display anything."""


def fan_out(*handlers: EventHandler) -> EventHandler:
    """One handler that passes every event to each of the given handlers."""

    def handle(event: AgentEvent) -> None:
        for handler in handlers:
            handler(event)

    return handle
