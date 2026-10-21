from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def now() -> datetime:
    return datetime.now(UTC)


class TraceEntry(BaseModel):
    """Fields every line of a trace file has."""

    run_id: str
    timestamp: datetime = Field(default_factory=now)


class RunStart(TraceEntry):
    type: Literal["run_start"] = "run_start"
    task_id: str | None = None  # the SWE-bench instance id; None for runs by hand
    task: str
    model: str
    graph_enabled: bool = False
    workspace: str
    repo_commit: str | None = None  # None when the workspace is not a git repo
    config: dict[str, Any]


class TraceAction(BaseModel):
    tool: str
    call_id: str
    # parsed JSON for a valid call; the raw text the model sent for an invalid one
    arguments: dict[str, Any] | str
    valid: bool


class Step(TraceEntry):
    type: Literal["step"] = "step"
    step: int
    reasoning_summary: list[str] = []
    reasoning: list[str] = []
    # the preamble next to a tool call, or the reply when there is no tool call
    text: str | None = None
    phase: str | None = None
    action: TraceAction | None = None
    observation: str | None = None
    blocked_rule: str | None = None
    # workspace-relative files this step's output showed the model; compared
    # against the gold patch to find steps-to-first-correct-file
    files_surfaced: list[str] = []
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    cost: float
    latency_seconds: float


class RunEnd(TraceEntry):
    type: Literal["run_end"] = "run_end"
    stop_reason: str
    steps: int
    total_tokens: int
    total_cost: float
