import re
from pathlib import PurePosixPath

from pydantic import BaseModel, Field

from agent.state import ToolName
from config.constants import ToolMessages
from mcp_server.errors import ToolError
from mcp_server.schemas import ToolSpecification
from mcp_server.workspace import Workspace


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
    workspace: Workspace,
    max_results: int,
) -> str:
    # check here so a bad pattern gets the same error locally and in a sandbox
    try:
        re.compile(pattern)
    except re.error as e:
        raise ToolError(ToolMessages.INVALID_REGEX.format(error=e)) from e

    if not workspace.exists(path):
        raise ToolError(ToolMessages.PATH_NOT_FOUND.format(path=path))

    matches = [
        f"{match.path}:{match.line_number}: {match.line}"
        for match in workspace.grep(pattern, path)
        if not include or PurePosixPath(match.path).match(include)
    ]

    if not matches:
        return ToolMessages.NO_MATCHES

    shown = matches[:max_results]
    if len(matches) > max_results:
        shown.append(
            ToolMessages.MATCHES_TRUNCATED.format(shown=max_results, total=len(matches))
        )
    return "\n".join(shown)
