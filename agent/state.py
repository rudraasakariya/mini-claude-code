from dataclasses import dataclass , field
from typing import Any

@dataclass
class Action:
    tool: str
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
    stop_reason: str | None = None