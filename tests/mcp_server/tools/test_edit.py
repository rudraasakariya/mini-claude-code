import pytest

from mcp_server.errors import ToolError
from mcp_server.tools.edit import edit_file
from mcp_server.workspace import LocalWorkspace


def test_edit_replaces_text_in_file(tmp_path):
    file = tmp_path / "app.py"
    file.write_text("x = 1\n")

    edit_file("app.py", "x = 1", "x = 2", workspace=LocalWorkspace(tmp_path))

    assert file.read_text() == "x = 2\n"


def test_edit_fails_when_old_string_not_found(tmp_path):
    file = tmp_path / "app.py"
    file.write_text("x = 1\n")

    with pytest.raises(ToolError):
        edit_file("app.py", "y = 5", "y = 6", workspace=LocalWorkspace(tmp_path))

    assert file.read_text() == "x = 1\n"  # nothing was written


def test_edit_fails_when_old_string_appears_twice(tmp_path):
    file = tmp_path / "app.py"
    file.write_text("x = 1\nx = 1\n")

    with pytest.raises(ToolError):
        edit_file("app.py", "x = 1", "x = 2", workspace=LocalWorkspace(tmp_path))

    assert file.read_text() == "x = 1\nx = 1\n"  # neither copy was replaced


def test_edit_fails_when_file_does_not_exist(tmp_path):
    with pytest.raises(ToolError):
        edit_file("missing.py", "x = 1", "x = 2", workspace=LocalWorkspace(tmp_path))


def test_edit_fails_when_path_escapes_workspace(tmp_path):
    # the workspace is a subfolder, so ../ points at a real file outside it
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("x = 1\n")

    with pytest.raises(ToolError):
        edit_file(
            "../outside.py", "x = 1", "x = 2", workspace=LocalWorkspace(workspace)
        )

    assert outside.read_text() == "x = 1\n"  # the file outside was not touched
