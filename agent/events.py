from collections.abc import Callable
from dataclasses import dataclass

from agent.state import Action, InvalidToolCall, LoopState, Message


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
class RunFinished:
    stop_reason: LoopState
    token_count: int
    spend: float


AgentEvent = (
    ModelCallStarted | ToolCallStarted | ToolCallFinished | AssistantText | RunFinished
)

# whoever shows the run (CLI, TUI, tests) passes one of these to the loop
EventHandler = Callable[[AgentEvent], None]


def ignore_event(event: AgentEvent) -> None:
    """Default handler for callers that don't display anything."""
