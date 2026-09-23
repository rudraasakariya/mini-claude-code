from pathlib import Path
from mcp_server.errors import ToolError


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
