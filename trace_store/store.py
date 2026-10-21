import logging
import re
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from agent.events import AgentEvent, RunFinished, StepFinished
from agent.state import Action, InvalidToolCall, TextTurn, ToolCallTurn, ToolName
from config.constants import ExecutorMessages, LogMessages, TraceFormat
from config.settings import RunConfig, TraceSettings
from trace_store.entries import RunEnd, RunStart, Step, TraceAction, TraceEntry

logger = logging.getLogger(__name__)


def new_run_id() -> str:
    """A run id for runs started by hand; SWE-bench runs use the task id."""
    return datetime.now(UTC).strftime(TraceFormat.RUN_ID_TIME_FORMAT)


def current_commit(root_path: Path) -> str | None:
    """The workspace's HEAD commit, or None if it is not a git repo."""
    try:
        result = subprocess.run(
            TraceFormat.GIT_HEAD_COMMAND,
            cwd=root_path,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None  # not a repo, or git is not installed
    return result.stdout.strip()


def to_relative(path: str, root_path: Path) -> str | None:
    """A path as the gold patch writes it: relative to the repo root."""
    full_path = (root_path / path).resolve()
    if not full_path.is_relative_to(root_path):
        return None
    return str(full_path.relative_to(root_path))


def files_surfaced(action: Action, observation: str, root_path: Path) -> list[str]:
    """The workspace files a tool's output showed the model, in order, no repeats."""
    if observation.startswith(ExecutorMessages.ERROR_PREFIX):
        return []  # a failed call showed nothing

    match action.tool:
        case ToolName.READ:
            paths = [str(action.arguments.get("file_path", ""))]
        case ToolName.GREP:
            paths = [
                match.group(1)
                for line in observation.splitlines()
                if (match := re.match(TraceFormat.GREP_LINE_PATH_REGEX, line))
            ]
        case ToolName.GLOB:
            paths = observation.splitlines()
        case _:
            paths = []  # run and edit don't search; graph tools add their own case

    relative = (to_relative(path, root_path) for path in paths if path)
    # dict keeps the first-seen order while dropping repeats
    return list(dict.fromkeys(path for path in relative if path is not None))


def to_trace_action(action: Action | InvalidToolCall) -> TraceAction:
    match action:
        case Action(tool=tool, call_id=call_id, arguments=arguments):
            return TraceAction(
                tool=tool.value, call_id=call_id, arguments=arguments, valid=True
            )
        case InvalidToolCall(name=name, call_id=call_id, arguments=arguments):
            return TraceAction(
                tool=name, call_id=call_id, arguments=arguments, valid=False
            )


class TraceRecorder:
    """Writes one run to its own JSONL file: run_start, one line per step, run_end."""

    def __init__(self, settings: TraceSettings, start: RunStart, root_path: Path):
        self.path = (
            settings.output_dir
            / settings.batch
            / f"{start.run_id}{TraceFormat.FILE_SUFFIX}"
        )
        self.run_id = start.run_id
        self.root_path = root_path
        self.steps = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.write(start)
        logger.info(LogMessages.TRACE_STARTED, extra={"trace_file": str(self.path)})

    def write(self, entry: TraceEntry) -> None:
        # open per line so every line is on disk even if the run crashes
        with self.path.open("a") as file:
            file.write(entry.model_dump_json() + "\n")

    def __call__(self, event: AgentEvent) -> None:
        match event:
            case StepFinished():
                self.write(self.to_step(event))
            case RunFinished(stop_reason=stop_reason):
                self.write(
                    RunEnd(
                        run_id=self.run_id,
                        stop_reason=stop_reason.value,
                        steps=self.steps,
                        total_tokens=self.total_tokens,
                        total_cost=self.total_cost,
                    )
                )
            case _:
                pass  # the other events are for the screen; StepFinished has it all

    def to_step(self, event: StepFinished) -> Step:
        self.steps += 1
        usage = event.usage
        self.total_tokens += usage.input_tokens + usage.output_tokens
        self.total_cost += usage.cost

        turn = event.turn
        reasoning = turn.reasoning
        step = Step(
            run_id=self.run_id,
            step=self.steps,
            reasoning_summary=reasoning.summary if reasoning else [],
            reasoning=reasoning.content if reasoning else [],
            blocked_rule=event.blocked_rule,
            input_tokens=usage.input_tokens,
            cached_tokens=usage.cached_tokens,
            output_tokens=usage.output_tokens,
            cost=usage.cost,
            latency_seconds=event.latency_seconds,
        )
        match turn:
            case ToolCallTurn(
                action=action, observation=observation, preamble=preamble
            ):
                step.action = to_trace_action(action)
                step.observation = observation
                if preamble is not None:
                    step.text = preamble.text
                    step.phase = preamble.phase.value if preamble.phase else None
                if isinstance(action, Action):
                    step.files_surfaced = files_surfaced(
                        action, observation, self.root_path
                    )
            case TextTurn(text=text, phase=phase):
                step.text = text
                step.phase = phase.value if phase else None
        return step


def open_trace(
    config: RunConfig,
    model: str,
    task: str,
    task_id: str | None = None,
    graph_enabled: bool = False,
) -> TraceRecorder:
    """Start the trace for one run; the run id is the task id when there is one."""
    root_path = config.workspace.root_path
    start = RunStart(
        run_id=task_id or new_run_id(),
        task_id=task_id,
        task=task,
        model=model,
        graph_enabled=graph_enabled,
        workspace=str(root_path),
        repo_commit=current_commit(root_path),
        config=asdict(config),
    )
    return TraceRecorder(config.trace, start, root_path)
