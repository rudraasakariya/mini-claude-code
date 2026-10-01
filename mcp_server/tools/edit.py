import difflib
from pathlib import Path

from pydantic import BaseModel, Field

from agent.state import ToolName
from config.constants import ToolMessages
from mcp_server.errors import ToolError
from mcp_server.schemas import ToolSpecification
from mcp_server.workspace import resolve_in_workspace


class EditArgs(BaseModel):
    file_path: str = Field(description="Path of the file to edit, relative to the project root.")
    old_string: str = Field(description="The string to be replaced in the file.")
    new_string: str = Field(description="The string to replace the old string with in the file.")


EDIT_TOOL_SPECIFICATION = ToolSpecification(
    name=ToolName.EDIT,
    description=(
        "Replace one exact piece of text in a file with new text. "
        "old_string must match the file exactly once, including whitespace. "
        "Use read first to copy the exact text. "
        "If it matches zero times or more than once the edit fails, so include more surrounding lines to make it unique. "
        "It returns a diff of the change."
    ),
    args=EditArgs,
)


def edit_file(file_path: str, old_string: str, new_string: str, *, root_path: Path) -> str:
    if old_string == new_string:
        raise ToolError(ToolMessages.EDIT_SAME_STRING)
    file = resolve_in_workspace(file_path, root_path)
    if not file.is_file():
        raise ToolError(ToolMessages.NOT_A_FILE.format(path=file_path))
    if not old_string:
        raise ToolError(ToolMessages.EDIT_EMPTY_OLD_STRING)

    content = file.read_text()
    count = content.count(old_string)
    if count == 0:
        raise ToolError(ToolMessages.EDIT_NOT_FOUND.format(path=file_path))
    if count > 1:
        raise ToolError(
            ToolMessages.EDIT_NOT_UNIQUE.format(count=count, path=file_path)
        )

    new_content = content.replace(old_string, new_string)
    file.write_text(new_content)
    diff = difflib.unified_diff(
        content.splitlines(),
        new_content.splitlines(),
        fromfile=ToolMessages.DIFF_BEFORE_LABEL.format(path=file_path),
        tofile=ToolMessages.DIFF_AFTER_LABEL.format(path=file_path),
        lineterm="",
    )
    return "\n".join(diff)
