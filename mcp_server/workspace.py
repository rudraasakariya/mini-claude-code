from pathlib import Path

from config.constants import ToolMessages
from mcp_server.errors import ToolError


def resolve_in_workspace(path: str, root_path: Path) -> Path:
    """
    Resolve a path the model gave against the workspace root, and refuse it
    if it ends up outside the root (via ../, an absolute path, or a symlink).
    """
    absolute_path = (root_path / path).resolve()
    if not absolute_path.is_relative_to(root_path):
        raise ToolError(
            ToolMessages.PATH_OUTSIDE_WORKSPACE.format(path=path, root=root_path)
        )
    return absolute_path
