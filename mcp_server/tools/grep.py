import re
from pathlib import Path

from pydantic import BaseModel, Field

from agent.state import ToolName
from config.constants import ToolMessages
from mcp_server.errors import ToolError
from mcp_server.project_files import list_project_files
from mcp_server.schemas import ToolSpecification
from mcp_server.workspace import resolve_in_workspace


class GrepArgs(BaseModel):
    pattern: str = Field(description="The regex pattern to search for.")
    path: str = Field(default=".", description="The root path to start searching from.")
    include: str | None = Field(
        default=None,
        description="A glob pattern to filter which files to search. If not provided, all files are searched.",
    )


GREP_TOOL_SPECIFICATION = ToolSpecification(
    name=ToolName.GREP,
    description=(
        "Search inside files for a regex pattern. Each match is returned as file:line: text. "
        "Use it to find where something is defined or used. "
        "It searches file contents, not file names, so use glob to find files by name. "
        "It does not show surrounding code, so use read on a match to see more. "
        "Results are capped, so narrow the pattern, path or include filter if the result says it was truncated."
    ),
    args=GrepArgs,
)


def grep(
    pattern: str,
    path: str = ".",
    include: str | None = None,
    *,
    root_path: Path,
    max_results: int,
) -> str:
    try:
        regex = re.compile(pattern)
    except re.error as e:
        raise ToolError(ToolMessages.INVALID_REGEX.format(error=e)) from e

    root = resolve_in_workspace(path, root_path)
    if not root.exists():
        raise ToolError(ToolMessages.PATH_NOT_FOUND.format(path=path))

    files = [root] if root.is_file() else list_project_files(root)

    matches: list[str] = []
    for file in files:
        if include and not file.match(include):
            continue
        try:
            text = file.read_text()
        except UnicodeDecodeError:
            continue  # binary file, nothing to search
        for number, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                matches.append(f"{file}:{number}: {line}")

    if not matches:
        return ToolMessages.NO_MATCHES

    shown = matches[:max_results]
    if len(matches) > max_results:
        shown.append(
            ToolMessages.MATCHES_TRUNCATED.format(shown=max_results, total=len(matches))
        )
    return "\n".join(shown)
