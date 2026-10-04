import logging
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.constants import EnvConfig


@dataclass(frozen=True)
class LoopSettings:
    max_steps: int = 30
    last_action_repeat_limit: int = 3
    max_consecutive_invalid_calls: int = 5


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
    max_timeout_seconds: int = 600


class AzureSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=EnvConfig.ENV_FILE, frozen=True)

    azure_base_url: str
    azure_deployment: str
    azure_api_key: SecretStr


@dataclass(frozen=True)
class OpenAISettings:
    max_retries: int = 5
    timeout_seconds: float = 600.0
    connect_timeout_seconds: float = 5.0


@dataclass(frozen=True)
class WorkSpaceSettings:
    root_path: Path = field(default_factory=lambda: Path.cwd().resolve())


@dataclass(frozen=True)
class LoggingSettings:
    level: int = logging.INFO


@dataclass(frozen=True)
class PriceTier:
    # USD per million tokens
    input: float
    cached_input: float
    cache_write: float
    output: float


@dataclass(frozen=True)
class PricingSettings:
    # gpt-6-luna, Azure Global Standard; a request above the threshold is
    # billed entirely at long-context prices
    long_context_threshold_tokens: int = 272_000
    short_context: PriceTier = PriceTier(
        input=0.10, cached_input=0.01, cache_write=0.125, output=0.50
    )
    long_context: PriceTier = PriceTier(
        input=0.20, cached_input=0.02, cache_write=0.25, output=0.75
    )
    tokens_per_price_unit: int = 1_000_000
