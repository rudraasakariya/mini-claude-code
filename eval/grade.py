import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from daytona import Daytona, DaytonaTimeoutError, Sandbox
from swebench.harness.constants import CONTAINER_PATCH_FILE
from swebench.harness.grading import get_eval_report
from swebench.harness.run_evaluation import GIT_APPLY_CMDS
from swebench.harness.utils import make_test_spec

from config.constants import GradeMessages, LogMessages
from config.logging_setup import configure_logging
from config.settings import (
    DaytonaSettings,
    LoggingSettings,
    SweBenchSettings,
    TraceSettings,
)
from eval.harness import load_tasks
from sandbox.container import make_daytona, task_sandbox

logger = logging.getLogger(__name__)


def apply_patch(sandbox: Sandbox, patch: str, settings: SweBenchSettings) -> bool:
    """Apply the model's patch the way the official harness does."""
    cwd = str(settings.repo_root)
    timeout = settings.harness_command_timeout_seconds
    sandbox.fs.upload_file(patch.encode(), CONTAINER_PATCH_FILE)
    for attempt, apply_command in enumerate(GIT_APPLY_CMDS):
        if attempt:
            sandbox.process.exec(GradeMessages.RESET_TREE, cwd=cwd, timeout=timeout)
        command = f"{apply_command} {CONTAINER_PATCH_FILE}"
        if sandbox.process.exec(command, cwd=cwd, timeout=timeout).exit_code == 0:
            return True
    # the chain can leave the patch applied while every command still failed
    check = GradeMessages.CHECK_ALREADY_APPLIED.format(patch=CONTAINER_PATCH_FILE)
    return sandbox.process.exec(check, cwd=cwd, timeout=timeout).exit_code == 0


def run_eval(sandbox: Sandbox, eval_script: str, settings: SweBenchSettings) -> str:
    """Run the task's official eval script and return its output."""
    sandbox.fs.upload_file(eval_script.encode(), GradeMessages.EVAL_SCRIPT_PATH)
    response = sandbox.process.exec(
        GradeMessages.RUN_EVAL_SCRIPT,
        cwd=str(settings.repo_root),
        timeout=settings.eval_timeout_seconds,
    )
    return response.result


def grade_task(
    task: dict[str, Any],
    prediction: dict[str, str],
    daytona: Daytona,
    settings: SweBenchSettings,
    logs_dir: Path,
) -> dict[str, Any]:
    """Grade one prediction; returns the official report plus why it failed early."""
    instance_id = task["instance_id"]
    if not prediction["model_patch"].strip():
        return {"resolved": False, "reason": GradeMessages.EMPTY_PATCH}

    test_spec = make_test_spec(task)
    log_path = logs_dir / f"{instance_id}{GradeMessages.LOG_SUFFIX}"
    # the eval script reinstalls the repo with pip, so grading keeps the network
    with task_sandbox(daytona, instance_id, settings, block_network=False) as sandbox:
        if not apply_patch(sandbox, prediction["model_patch"], settings):
            return {"resolved": False, "reason": GradeMessages.PATCH_APPLY_FAILED}
        try:
            output = run_eval(sandbox, test_spec.eval_script, settings)
        except DaytonaTimeoutError:
            log_path.write_text(
                GradeMessages.TIMEOUT_NOTE.format(timeout=settings.eval_timeout_seconds)
            )
            return {"resolved": False, "reason": GradeMessages.TIMED_OUT}
    log_path.write_text(output)
    report = get_eval_report(
        test_spec=test_spec,
        prediction=prediction,
        test_log_path=str(log_path),
        include_tests_status=True,
    )
    return report[instance_id]


def safe_grade_task(
    task: dict[str, Any],
    prediction: dict[str, str],
    daytona: Daytona,
    settings: SweBenchSettings,
    logs_dir: Path,
) -> dict[str, Any]:
    instance_id = task["instance_id"]
    logger.info(LogMessages.GRADE_STARTED, extra={"instance_id": instance_id})
    try:
        result = grade_task(task, prediction, daytona, settings, logs_dir)
    except Exception:
        # one broken task must not end the batch; it counts as unresolved
        logger.exception(LogMessages.GRADE_FAILED, extra={"instance_id": instance_id})
        result = {"resolved": False, "reason": GradeMessages.CRASHED}
    logger.info(
        LogMessages.GRADE_FINISHED,
        extra={"instance_id": instance_id, "resolved": result["resolved"]},
    )
    return result


def main() -> None:
    settings = SweBenchSettings()
    parser = argparse.ArgumentParser(description=GradeMessages.DESCRIPTION)
    parser.add_argument("--batch", required=True, help=GradeMessages.BATCH_HELP)
    parser.add_argument(
        "--workers",
        type=int,
        default=settings.grade_workers,
        help=GradeMessages.WORKERS_HELP,
    )
    args = parser.parse_args()

    configure_logging(LoggingSettings())
    batch_dir = TraceSettings().output_dir / args.batch
    logs_dir = batch_dir / settings.grade_logs_dir_name
    logs_dir.mkdir(parents=True, exist_ok=True)

    predictions_path = batch_dir / settings.predictions_file_name
    predictions = {
        prediction["instance_id"]: prediction
        for prediction in map(json.loads, predictions_path.read_text().splitlines())
    }
    tasks = load_tasks(settings, list(predictions), limit=None)
    daytona = make_daytona(DaytonaSettings())  # type: ignore[call-arg]

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            task["instance_id"]: pool.submit(
                safe_grade_task,
                task,
                predictions[task["instance_id"]],
                daytona,
                settings,
                logs_dir,
            )
            for task in tasks
        }
        results = {
            instance_id: future.result() for instance_id, future in futures.items()
        }

    resolved = sum(result["resolved"] for result in results.values())
    summary = {"resolved": resolved, "total": len(results), "instances": results}
    (batch_dir / settings.results_file_name).write_text(json.dumps(summary, indent=2))
    logger.info(
        LogMessages.GRADE_SUMMARY, extra={"resolved": resolved, "total": len(results)}
    )


if __name__ == "__main__":
    main()
