from pathlib import PurePosixPath

from pydantic import BaseModel, Field

from agent.state import ToolName
from config.constants import ToolMessages
from mcp_server.errors import ToolError
from mcp_server.schemas import ToolSpecification
from mcp_server.workspace import Workspace


class GlobArgs(BaseModel):
    pattern: str = Field(description="The glob pattern to search for.")
    path: str = Field(default=".", description="The root path to start searching from.")


GLOB_TOOL_SPECIFICATION = ToolSpecification(
    name=ToolName.GLOB,
    description=(
        "Find files by name using a glob pattern such as *.py or test_*.py. "
        "It matches file names only, so use grep to search inside files. "
        "It returns paths, not file contents, so use read to see a file. "
        "Results are capped, so use a narrower pattern or path if the result says it was truncated."
    ),
    args=GlobArgs,
)


def glob(
    pattern: str, path: str = ".", *, workspace: Workspace, max_results: int
) -> str:
    if not workspace.exists(path):
        raise ToolError(ToolMessages.PATH_NOT_FOUND.format(path=path))

    results = [
        file
        for file in workspace.list_files(path)
        if PurePosixPath(file).match(pattern)
    ]

    if not results:
        return ToolMessages.NO_MATCHES

    shown = results[:max_results]
    if len(results) > max_results:
        shown.append(
            ToolMessages.MATCHES_TRUNCATED.format(shown=max_results, total=len(results))
        )
    return "\n".join(shown)
