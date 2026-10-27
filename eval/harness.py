import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Any

from datasets import load_dataset
from daytona import Daytona
from openai import OpenAI

from agent.loop import run_agent_loop
from agent.state import State, UserTurn
from config.constants import (
    EvalMessages,
    LogMessages,
    Prompts,
    SecretNames,
    TraceFormat,
)
from config.logging_setup import configure_logging
from config.settings import (
    MODEL_PRICING,
    AzureSettings,
    DaytonaSettings,
    LoggingSettings,
    OpenAISettings,
    RunConfig,
    SweBenchSettings,
    TraceSettings,
    WorkSpaceSettings,
)
from hooks.guardrails import Guardrails
from hooks.policy import load_policy
from mcp_server.workspace import DaytonaWorkspace
from router.azure_client import make_client
from sandbox.container import make_daytona, task_sandbox
from trace_store.entries import RunEnd
from trace_store.store import open_trace

logger = logging.getLogger(__name__)


def load_tasks(
    settings: SweBenchSettings, instance_ids: list[str], limit: int | None
) -> list[dict[str, Any]]:
    dataset = load_dataset(settings.dataset, split=settings.split)
    tasks = [dict(row) for row in dataset]
    if instance_ids:
        wanted = set(instance_ids)
        tasks = [task for task in tasks if task["instance_id"] in wanted]
    return tasks[:limit] if limit else tasks


def read_split(name: str, settings: SweBenchSettings) -> list[str]:
    path = settings.splits_dir / f"{name}{settings.split_suffix}"
    return [line for line in path.read_text().splitlines() if line]


def finished_ids(predictions_path: Path) -> set[str]:
    """Tasks that reached a recorded end and saved a patch; a rerun skips them."""
    if not predictions_path.exists():
        return set()
    saved = {
        json.loads(line)["instance_id"]
        for line in predictions_path.read_text().splitlines()
    }
    run_end = RunEnd.model_fields["type"].default
    finished = set()
    for instance_id in saved:
        trace = predictions_path.parent / f"{instance_id}{TraceFormat.FILE_SUFFIX}"
        if trace.exists() and any(
            json.loads(line)["type"] == run_end
            for line in trace.read_text().splitlines()
        ):
            finished.add(instance_id)
    return finished


def solve_task(
    task: dict[str, Any],
    client: OpenAI,
    model: str,
    config: RunConfig,
    guardrails: Guardrails,
    workspace: DaytonaWorkspace,
    settings: SweBenchSettings,
) -> str:
    """Run the agent on one task and return its patch, however the run ended."""
    prompt = Prompts.SWE_TASK.format(issue=task["problem_statement"])
    state = State(conversation=[UserTurn(prompt)])
    recorder = open_trace(
        config, workspace, model, task=prompt, task_id=task["instance_id"]
    )
    run_agent_loop(
        client, model, state, config, guardrails, workspace, on_event=recorder
    )
    diff = workspace.run(
        EvalMessages.GIT_DIFF_COMMAND, settings.harness_command_timeout_seconds
    )
    return diff.stdout


def run_task(
    task: dict[str, Any],
    client: OpenAI,
    model: str,
    config: RunConfig,
    guardrails: Guardrails,
    daytona: Daytona,
    settings: SweBenchSettings,
    predictions_path: Path,
    write_lock: Lock,
) -> None:
    """Solve one task in its own sandbox and append its prediction."""
    instance_id = task["instance_id"]
    logger.info(LogMessages.TASK_STARTED, extra={"instance_id": instance_id})
    # a crashed earlier attempt left a partial trace; traces append, so start clean
    trace = predictions_path.parent / f"{instance_id}{TraceFormat.FILE_SUFFIX}"
    trace.unlink(missing_ok=True)
    try:
        with task_sandbox(daytona, instance_id, settings) as sandbox:
            workspace = DaytonaWorkspace(
                sandbox,
                settings.repo_root,
                settings.harness_command_timeout_seconds,
                env={EvalMessages.PATH_VARIABLE: settings.path},
            )
            patch = solve_task(
                task, client, model, config, guardrails, workspace, settings
            )
    except Exception:
        # one broken task must not end the batch; it counts as unsolved
        logger.exception(LogMessages.TASK_FAILED, extra={"instance_id": instance_id})
        patch = ""
    prediction = {
        "instance_id": instance_id,
        "model_name_or_path": settings.model_name,
        "model_patch": patch,
    }
    # workers finish in any order; the lock keeps each line whole
    with write_lock, predictions_path.open("a") as file:
        file.write(json.dumps(prediction) + "\n")
    logger.info(
        LogMessages.TASK_FINISHED,
        extra={"instance_id": instance_id, "patch_chars": len(patch)},
    )


def main() -> None:
    settings = SweBenchSettings()
    parser = argparse.ArgumentParser(description=EvalMessages.DESCRIPTION)
    parser.add_argument("--batch", required=True, help=EvalMessages.BATCH_HELP)
    parser.add_argument("--split", default=None, help=EvalMessages.SPLIT_HELP)
    parser.add_argument(
        "--instance", action="append", default=[], help=EvalMessages.INSTANCE_HELP
    )
    parser.add_argument("--limit", type=int, default=None, help=EvalMessages.LIMIT_HELP)
    parser.add_argument(
        "--workers",
        type=int,
        default=settings.solve_workers,
        help=EvalMessages.WORKERS_HELP,
    )
    parser.add_argument("--model", default=None, help=EvalMessages.MODEL_HELP)
    args = parser.parse_args()

    configure_logging(LoggingSettings())
    azure = AzureSettings()  # type: ignore[call-arg]
    model = args.model or azure.azure_deployment
    config = RunConfig(
        workspace=WorkSpaceSettings(root_path=settings.repo_root),
        trace=TraceSettings(batch=args.batch),
        # a KeyError here means the model has no prices yet; never guess them
        pricing=MODEL_PRICING[model],
    )
    daytona_settings = DaytonaSettings()  # type: ignore[call-arg]
    client = make_client(azure, OpenAISettings())
    guardrails = Guardrails(
        policy=load_policy(config.policy),
        secrets={
            SecretNames.AZURE_API_KEY: azure.azure_api_key.get_secret_value(),
            SecretNames.DAYTONA_API_KEY: daytona_settings.daytona_api_key.get_secret_value(),
        },
    )
    daytona = make_daytona(daytona_settings)

    predictions_path: Path = (
        config.trace.output_dir / args.batch / settings.predictions_file_name
    )
    predictions_path.parent.mkdir(parents=True, exist_ok=True)

    instance_ids = list(args.instance)
    if args.split:
        instance_ids += read_split(args.split, settings)
    tasks = load_tasks(settings, instance_ids, args.limit)
    done = finished_ids(predictions_path)
    if done:
        logger.info(LogMessages.TASKS_SKIPPED, extra={"skipped": len(done)})
        tasks = [task for task in tasks if task["instance_id"] not in done]
    write_lock = Lock()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for task in tasks:
            pool.submit(
                run_task,
                task,
                client,
                model,
                config,
                guardrails,
                daytona,
                settings,
                predictions_path,
                write_lock,
            )


if __name__ == "__main__":
    main()
