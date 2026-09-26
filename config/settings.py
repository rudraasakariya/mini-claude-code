from dataclasses import dataclass
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    max_run_output_chars: int = 10000


class AzureSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", frozen=True)

    azure_base_url: str
    azure_deployment: str
    azure_api_key: SecretStr