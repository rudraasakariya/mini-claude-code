from pathlib import Path

import pytest

from mcp_server.errors import ToolError
from mcp_server.tools.glob import glob
from mcp_server.tools.grep import grep
from mcp_server.workspace import DaytonaWorkspace, LocalWorkspace


def make_repo(root: Path) -> LocalWorkspace:
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("def add(a, b):\n    return a - b\n")
    return LocalWorkspace(root)


def test_grep_prints_paths_relative_to_the_root(tmp_path):
    workspace = make_repo(tmp_path)
    result = grep("def add", workspace=workspace, max_results=10)
    assert result == "src/app.py:1: def add(a, b):"


def test_glob_prints_paths_relative_to_the_root(tmp_path):
    workspace = make_repo(tmp_path)
    assert glob("*.py", workspace=workspace, max_results=10) == "src/app.py"


@pytest.mark.parametrize("path", ["../etc/passwd", "/etc/passwd", "src/../../x"])
def test_sandbox_paths_cannot_leave_the_repo(path):
    # resolving needs no sandbox, so none is passed
    workspace = DaytonaWorkspace(None, Path("/testbed"), command_timeout=1)  # type: ignore[arg-type]
    with pytest.raises(ToolError):
        workspace.is_file(path)
