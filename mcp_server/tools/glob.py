from pathlib import Path
from mcp_server.errors import ToolError
from mcp_server.schemas import ToolSpec
from agent.state import ToolName
from pydantic import BaseModel, Field

IGNORED_DIRS = {".git", "__pycache__", "node_modules"}
NO_MATCHES_MESSAGE = "No matches found."
TRUNCATION_NOTICE = (
    "[truncated: showing {shown} of {total} matches. "
    "Narrow the pattern, path.]"
)


class GlobArgs(BaseModel):
    pattern: str = Field(description="The glob pattern to search for.")
    path: str = Field(default=".", description="The root path to start searching from.")

GLOB_SPEC = ToolSpec(
    name=ToolName.GLOB,
    description=(
        "Find files by name using a glob pattern such as *.py or test_*.py. "
        "It matches file names only, so use grep to search inside files. "
        "It returns paths, not file contents, so use read to see a file. "
        "Results are capped, so use a narrower pattern or path if the result says it was truncated."
    ),
    args=GlobArgs,
)



def glob(pattern: str, path: str = ".", *, max_results: int) -> str:
    root = Path(path)
    if not root.exists():
        raise ToolError(
            f"The path {path} does not exist. Use glob or grep to search for the right path."
        )
    results: list[str] = []
    for file in root.rglob(pattern):
        if not file.is_file():
            continue
        if any(part in IGNORED_DIRS for part in file.parts):
            continue

        results.append(str(file))
    if not results:
        return NO_MATCHES_MESSAGE
    glob_results = results[:max_results]
    if len(results) > max_results:
        glob_results.append(
            TRUNCATION_NOTICE.format(shown=max_results, total=len(results))
        )
    return "\n".join(glob_results)
