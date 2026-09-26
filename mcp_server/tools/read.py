from pathlib import Path

from pydantic import BaseModel, Field

from agent.state import ToolName
from mcp_server.errors import ToolError
from mcp_server.schemas import ToolSpec


class ReadArgs(BaseModel):
    file_path: str = Field(description="Path of the file to read, relative to the project root.")
    start_line: int = Field(description="First line to read. Lines start at 1.")
    end_line: int = Field(description="Last line to read, inclusive.")


READ_SPEC = ToolSpec(
    name=ToolName.READ,
    description=(
        "Read a range of lines from one file. Each line is returned with its line number. "
        "Use it after grep or glob has told you which file to look at. "
        "It cannot list directories or search. Very large ranges are cut off, "
        "so ask for a narrower range if the result says it was truncated."
    ),
    args=ReadArgs,
)


def read_file(file_path: str, start_line: int, end_line: int, *, max_lines: int) -> str:
    path = Path(file_path)
    if not path.is_file():
        raise ToolError(f"The path {file_path} is not a valid file.")

    if start_line < 1 or end_line < start_line:
        raise ToolError("Invalid line range specified.")

    lines = path.read_text().splitlines()[start_line - 1 : end_line]
    numbered = [
        f"{number}: {line}" for number, line in enumerate(lines, start=start_line)
    ]
    if len(numbered) > max_lines:
        numbered = numbered[:max_lines]
        numbered.append(
            f"[truncated: showing {max_lines} of {len(lines)} lines. Narrow the line range.]"
        )

    return "\n".join(numbered)
