from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    max_steps: int = 30
    max_tokens: int = 100000
    max_spend: float = 1.00