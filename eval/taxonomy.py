import argparse
import json
import logging
import re
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from agent.state import LoopState, ToolName
from config.constants import ExecutorMessages, LogMessages, TaxonomyMessages
from config.logging_setup import configure_logging
from config.settings import LoggingSettings, SweBenchSettings, TraceSettings
from eval.harness import load_tasks

logger = logging.getLogger(__name__)


class Source(Enum):
    RULE = "rule"  # decided by the checks below, no judgment needed
    HAND = "hand"  # labelled by a person in hand_labels.json
    PENDING = "pending"  # still needs a person (or later, the LLM judge)


class RuleLabel(Enum):
    """Labels a rule can decide; the rest of the taxonomy needs judgment."""

    LOOP_STOPPED = "loop_stopped"  # step, token or cost limit, or another loop stop
    EDIT_DID_NOT_APPLY = "edit_did_not_apply"
    PATCH_BROKE_OTHER_TESTS = "patch_broke_other_tests"
    WRONG_FILE_LOCATED = "wrong_file_located"
    TESTS_NEVER_RUN = "tests_never_run"
    HOOK_BLOCKED = "hook_blocked"


@dataclass
class Failure:
    instance_id: str
    label: str | None
    source: str
    evidence: str


def patch_files(patch: str) -> set[str]:
    return set(re.findall(TaxonomyMessages.DIFF_FILE_REGEX, patch, re.MULTILINE))


def read_trace(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    steps = [line for line in lines if line["type"] == "step"]
    ends = [line for line in lines if line["type"] == "run_end"]
    return steps, ends[0] if ends else None


def tool_of(step: dict[str, Any]) -> str | None:
    action = step.get("action")
    return action["tool"] if action else None


def failed(step: dict[str, Any]) -> bool:
    return (step.get("observation") or "").startswith(ExecutorMessages.ERROR_PREFIX)


def ran_tests_after_last_edit(steps: list[dict[str, Any]]) -> bool:
    edits = [
        i
        for i, step in enumerate(steps)
        if tool_of(step) == ToolName.EDIT.value and not failed(step)
    ]
    if not edits:
        return False
    return any(
        tool_of(step) == ToolName.RUN.value
        and not str(step["action"]["arguments"].get("command", "")).startswith(
            TaxonomyMessages.GIT_COMMAND_PREFIX
        )
        for step in steps[edits[-1] + 1 :]
    )


def apply_rules(
    result: dict[str, Any],
    patch: str,
    gold_patch: str,
    steps: list[dict[str, Any]],
    end: dict[str, Any] | None,
) -> tuple[RuleLabel, str] | None:
    """The first rule that matches is the primary cause; order is priority."""
    if end is None or end["stop_reason"] != LoopState.FINAL_ANSWER_GIVEN.value:
        reason = end["stop_reason"] if end else TaxonomyMessages.NO_RUN_END
        return RuleLabel.LOOP_STOPPED, reason

    blocked = [step["blocked_rule"] for step in steps if step.get("blocked_rule")]
    if blocked:
        return RuleLabel.HOOK_BLOCKED, ", ".join(blocked)

    failed_edits = sum(
        1 for step in steps if tool_of(step) == ToolName.EDIT.value and failed(step)
    )
    if not patch.strip() or not result.get("patch_successfully_applied", True):
        return RuleLabel.EDIT_DID_NOT_APPLY, f"failed edits: {failed_edits}"

    broken = result.get("tests_status", {}).get("PASS_TO_PASS", {}).get("failure", [])
    if broken:
        return RuleLabel.PATCH_BROKE_OTHER_TESTS, ", ".join(broken[:5])

    ours, gold = patch_files(patch), patch_files(gold_patch)
    if not ours & gold:
        return (
            RuleLabel.WRONG_FILE_LOCATED,
            f"ours: {sorted(ours)} gold: {sorted(gold)}",
        )

    if not ran_tests_after_last_edit(steps):
        return RuleLabel.TESTS_NEVER_RUN, TaxonomyMessages.NO_RUN_AFTER_EDIT
    return None


def review_entry(
    task: dict[str, Any],
    patch: str,
    result: dict[str, Any],
    steps: list[dict[str, Any]],
) -> str:
    """Everything needed to label one failure by hand, as markdown."""
    tests = result.get("tests_status", {}).get("FAIL_TO_PASS", {})
    final = next((step.get("text") for step in reversed(steps) if step.get("text")), "")
    limit = TaxonomyMessages.ISSUE_CHARS
    return TaxonomyMessages.REVIEW_TEMPLATE.format(
        instance_id=task["instance_id"],
        issue=task["problem_statement"][:limit],
        ours=patch,
        gold=task["patch"],
        failing="\n".join(tests.get("failure", [])) or TaxonomyMessages.NONE,
        passing=len(tests.get("success", [])),
        total=len(tests.get("success", [])) + len(tests.get("failure", [])),
        steps=len(steps),
        final=final,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=TaxonomyMessages.DESCRIPTION)
    parser.add_argument("--batch", required=True, help=TaxonomyMessages.BATCH_HELP)
    args = parser.parse_args()

    configure_logging(LoggingSettings())
    settings = SweBenchSettings()
    batch_dir = TraceSettings().output_dir / args.batch
    results = json.loads((batch_dir / settings.results_file_name).read_text())
    predictions = {
        prediction["instance_id"]: prediction["model_patch"]
        for prediction in map(
            json.loads,
            (batch_dir / settings.predictions_file_name).read_text().splitlines(),
        )
    }
    hand_labels_path = batch_dir / TaxonomyMessages.HAND_LABELS_FILE
    hand_labels: dict[str, str] = (
        json.loads(hand_labels_path.read_text()) if hand_labels_path.exists() else {}
    )

    unresolved = [
        instance_id
        for instance_id, result in results["instances"].items()
        if not result["resolved"]
    ]
    tasks = {
        task["instance_id"]: task for task in load_tasks(settings, unresolved, None)
    }

    failures: list[Failure] = []
    review: list[str] = []
    for instance_id in sorted(unresolved):
        task, result, patch = (
            tasks[instance_id],
            results["instances"][instance_id],
            predictions[instance_id],
        )
        steps, end = read_trace(
            batch_dir / f"{instance_id}{TaxonomyMessages.TRACE_SUFFIX}"
        )
        ruled = apply_rules(result, patch, task["patch"], steps, end)
        if ruled is not None:
            label, evidence = ruled
            failures.append(
                Failure(instance_id, label.value, Source.RULE.value, evidence)
            )
        elif instance_id in hand_labels:
            failures.append(
                Failure(instance_id, hand_labels[instance_id], Source.HAND.value, "")
            )
        else:
            failures.append(Failure(instance_id, None, Source.PENDING.value, ""))
            review.append(review_entry(task, patch, result, steps))

    (batch_dir / TaxonomyMessages.OUTPUT_FILE).write_text(
        json.dumps([asdict(failure) for failure in failures], indent=2)
    )
    (batch_dir / TaxonomyMessages.REVIEW_FILE).write_text("\n".join(review))

    counts: dict[str, int] = {}
    for failure in failures:
        key = failure.label or Source.PENDING.value
        counts[key] = counts.get(key, 0) + 1
    logger.info(
        LogMessages.TAXONOMY_SUMMARY,
        extra={"unresolved": len(failures), "labels": counts},
    )


if __name__ == "__main__":
    main()
