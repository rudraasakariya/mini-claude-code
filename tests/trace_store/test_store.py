import json

import pytest

from agent.events import RunFinished, StepFinished, StepUsage
from agent.state import (
    Action,
    LoopState,
    MessagePhase,
    TextTurn,
    ToolCallTurn,
    ToolName,
)
from config.constants import ExecutorMessages
from config.settings import TraceSettings
from trace_store.entries import RunStart
from trace_store.store import TraceRecorder, files_surfaced


def action(tool: ToolName, **arguments) -> Action:
    return Action(tool=tool, call_id="call", arguments=arguments)


def test_read_surfaces_the_file_it_opened(tmp_path):
    result = files_surfaced(
        action(ToolName.READ, file_path="src/app.py"), "1: x", tmp_path
    )
    assert result == ["src/app.py"]


def test_grep_surfaces_each_matching_file_once(tmp_path):
    # grep prints absolute paths; the trace keeps them relative to the repo
    observation = "\n".join(
        [
            f"{tmp_path}/src/app.py:3: x = 1",
            f"{tmp_path}/src/app.py:9: x = 2",
            f"{tmp_path}/tests/test_app.py:1: import app",
        ]
    )
    result = files_surfaced(action(ToolName.GREP, pattern="x"), observation, tmp_path)
    assert result == ["src/app.py", "tests/test_app.py"]


def test_glob_surfaces_every_listed_file(tmp_path):
    observation = f"{tmp_path}/a.py\n{tmp_path}/b.py"
    result = files_surfaced(
        action(ToolName.GLOB, pattern="*.py"), observation, tmp_path
    )
    assert result == ["a.py", "b.py"]


def test_failed_call_surfaces_nothing(tmp_path):
    observation = f"{ExecutorMessages.ERROR_PREFIX}file not found"
    result = files_surfaced(
        action(ToolName.READ, file_path="x.py"), observation, tmp_path
    )
    assert result == []


def test_files_outside_the_workspace_are_dropped(tmp_path):
    result = files_surfaced(
        action(ToolName.READ, file_path="../x.py"), "1: x", tmp_path
    )
    assert result == []


def read_lines(recorder: TraceRecorder) -> list[dict]:
    return [json.loads(line) for line in recorder.path.read_text().splitlines()]


def test_recorder_writes_start_steps_and_end(tmp_path):
    settings = TraceSettings(output_dir=tmp_path, batch="dev")
    start = RunStart(
        run_id="django-1", task="fix it", model="m", workspace=str(tmp_path), config={}
    )
    recorder = TraceRecorder(settings, start, root_path=tmp_path)

    read = ToolCallTurn(
        action=action(ToolName.READ, file_path="app.py"), observation="1: x"
    )
    recorder(
        StepFinished(turn=read, usage=StepUsage(10, 0, 5, 0.01), latency_seconds=1.0)
    )
    reply = TextTurn(text="done", phase=MessagePhase.FINAL_ANSWER)
    recorder(
        StepFinished(turn=reply, usage=StepUsage(20, 10, 5, 0.02), latency_seconds=1.0)
    )
    recorder(
        RunFinished(stop_reason=LoopState.FINAL_ANSWER_GIVEN, token_count=0, spend=0)
    )

    assert recorder.path == tmp_path / "dev" / "django-1.jsonl"
    lines = read_lines(recorder)
    assert [line["type"] for line in lines] == ["run_start", "step", "step", "run_end"]
    assert lines[1]["action"]["tool"] == "read"
    assert lines[1]["files_surfaced"] == ["app.py"]
    assert lines[2]["text"] == "done"
    # totals are this run's own, not the whole session's
    assert lines[3]["steps"] == 2
    assert lines[3]["total_tokens"] == 40
    assert lines[3]["total_cost"] == pytest.approx(0.03)
