import argparse
import json
import logging
from pathlib import Path
from typing import Any

from datasets import load_dataset
from openai import OpenAI

from agent.loop import run_agent_loop
from agent.state import State, UserTurn
from config.constants import EvalMessages, LogMessages, Prompts, SecretNames
from config.logging_setup import configure_logging
from config.settings import (
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


def main() -> None:
    parser = argparse.ArgumentParser(description=EvalMessages.DESCRIPTION)
    parser.add_argument("--batch", required=True, help=EvalMessages.BATCH_HELP)
    parser.add_argument(
        "--instance", action="append", default=[], help=EvalMessages.INSTANCE_HELP
    )
    parser.add_argument("--limit", type=int, default=None, help=EvalMessages.LIMIT_HELP)
    args = parser.parse_args()

    configure_logging(LoggingSettings())
    settings = SweBenchSettings()
    config = RunConfig(
        workspace=WorkSpaceSettings(root_path=settings.repo_root),
        trace=TraceSettings(batch=args.batch),
    )
    azure = AzureSettings()  # type: ignore[call-arg]
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

    for task in load_tasks(settings, args.instance, args.limit):
        instance_id = task["instance_id"]
        logger.info(LogMessages.TASK_STARTED, extra={"instance_id": instance_id})
        try:
            with task_sandbox(daytona, instance_id, settings) as sandbox:
                workspace = DaytonaWorkspace(
                    sandbox,
                    settings.repo_root,
                    settings.harness_command_timeout_seconds,
                    env={EvalMessages.PATH_VARIABLE: settings.path},
                )
                patch = solve_task(
                    task,
                    client,
                    azure.azure_deployment,
                    config,
                    guardrails,
                    workspace,
                    settings,
                )
        except Exception:
            # one broken task must not end the batch; it counts as unsolved
            logger.exception(
                LogMessages.TASK_FAILED, extra={"instance_id": instance_id}
            )
            patch = ""
        prediction = {
            "instance_id": instance_id,
            "model_name_or_path": settings.model_name,
            "model_patch": patch,
        }
        with predictions_path.open("a") as file:
            file.write(json.dumps(prediction) + "\n")
        logger.info(
            LogMessages.TASK_FINISHED,
            extra={"instance_id": instance_id, "patch_chars": len(patch)},
        )


if __name__ == "__main__":
    main()
