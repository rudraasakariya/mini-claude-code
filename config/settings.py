from dataclasses import dataclass


@dataclass(frozen=True)
class LoopSettings:
    max_steps: int = 30
    last_action_repeat_limit: int = 3


@dataclass(frozen=True)
class BudgetSettings:
    max_tokens: int = 100000
    max_spend: float = 1.00


@dataclass(frozen=True)
class ToolSettings:
    max_grep_results: int = 100
    max_read_lines: int = 200
    max_glob_results: int = 100
