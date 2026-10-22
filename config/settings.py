import logging
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.constants import EnvConfig, TraceFormat


@dataclass(frozen=True)
class LoopSettings:
    max_steps: int = 100
    last_action_repeat_limit: int = 3
    max_consecutive_invalid_calls: int = 5


@dataclass(frozen=True)
class BudgetSettings:
    max_tokens: int = 1_000_000
    max_spend: float = 5.00


@dataclass(frozen=True)
class ToolSettings:
    max_grep_results: int = 100
    max_read_lines: int = 200
    max_glob_results: int = 100
    max_run_output_chars: int = 10000
    max_timeout_seconds: int = 600


class AzureSettings(BaseSettings):
    # .env belongs to the harness, so find it next to this code rather than in
    # the folder the agent was launched from (e.g. /testbed)
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / EnvConfig.ENV_FILE,
        frozen=True,
        extra="ignore",  # .env also holds other services' keys
    )

    azure_base_url: str
    azure_deployment: str
    azure_api_key: SecretStr


class DaytonaSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / EnvConfig.ENV_FILE,
        frozen=True,
        extra="ignore",
    )

    daytona_api_url: str
    daytona_api_key: SecretStr


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
    # None sends logs to stderr; the TUI sets a file so logs don't draw over it
    log_file: Path | None = None
    # libraries that log every HTTP request at INFO; only their warnings are kept
    quiet_loggers: tuple[str, ...] = ("httpx", "httpx2", "httpcore")


@dataclass(frozen=True)
class UiSettings:
    max_result_lines: int = 40  # longer tool results are cut in the display
    max_argument_chars: int = 120  # tool-call lines show this much of the arguments
    log_file: Path = field(
        default_factory=lambda: (
            Path(__file__).resolve().parent.parent / "logs" / "mclaude.log"
        )
    )


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


@dataclass(frozen=True)
class PolicySettings:
    # found next to this file, not in the workspace, so it works from any
    # launch folder (e.g. /testbed) and sits outside what the agent may edit
    path: Path = field(default_factory=lambda: Path(__file__).parent / "policy.json")


@dataclass(frozen=True)
class ProtectedPathSettings:
    # the harness's own folder (this file is <harness>/config/settings.py)
    harness_root: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent
    )
    # folders that are never edited, wherever they appear
    protected_dir_names: tuple[str, ...] = (".git",)


@dataclass(frozen=True)
class TraceSettings:
    # inside the harness folder, so traces never land in the repo being fixed
    output_dir: Path = field(
        default_factory=lambda: (
            Path(__file__).resolve().parent.parent / TraceFormat.RUNS_DIR_NAME
        )
    )
    batch: str = TraceFormat.INTERACTIVE_BATCH


@dataclass(frozen=True)
class SweBenchSettings:
    # the SWE-bench org's copy also carries each task's image and eval script
    dataset: str = "SWE-bench/SWE-bench_Lite"
    split: str = "test"
    # official eval images on Docker Hub; "__" in the id becomes "_1776_"
    image_template: str = "swebench/sweb.eval.x86_64.{instance}:latest"
    instance_separator: str = "__"
    image_separator: str = "_1776_"
    repo_root: Path = Path("/testbed")
    # the task's own Python comes first, so the agent's python and pytest are it
    path: str = (
        "/opt/miniconda3/envs/testbed/bin:/opt/miniconda3/bin:"
        "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    )
    sandbox_create_timeout_seconds: float = 1800
    harness_command_timeout_seconds: int = 120
    predictions_file_name: str = "predictions.jsonl"
    model_name: str = "mini-claude-code"
    # grading: the official harness's default test timeout
    eval_timeout_seconds: int = 1800
    grade_workers: int = 4
    grade_logs_dir_name: str = "logs"
    results_file_name: str = "results.json"


@dataclass(frozen=True)
class RunConfig:
    """Every settings group a run needs, built once at startup."""

    loop: LoopSettings = field(default_factory=LoopSettings)
    budget: BudgetSettings = field(default_factory=BudgetSettings)
    tools: ToolSettings = field(default_factory=ToolSettings)
    workspace: WorkSpaceSettings = field(default_factory=WorkSpaceSettings)
    pricing: PricingSettings = field(default_factory=PricingSettings)
    policy: PolicySettings = field(default_factory=PolicySettings)
    protected_paths: ProtectedPathSettings = field(
        default_factory=ProtectedPathSettings
    )
    trace: TraceSettings = field(default_factory=TraceSettings)
