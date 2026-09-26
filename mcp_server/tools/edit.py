from pathlib import Path
from mcp_server.errors import ToolError
import difflib
from mcp_server.schemas import ToolSpec
from agent.state import ToolName
from pydantic import BaseModel, Field


class EditArgs(BaseModel):
  file_path: str = Field(description="Path of the file to edit, relative to the project root.")
  old_string: str = Field(description="The string to be replaced in the file.")
  new_string: str = Field(description="The string to replace the old string with in the file.")

EDIT_SPEC = ToolSpec(
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

def edit_file(file_path: str, old_string: str, new_string: str) -> str:
    if old_string == new_string:
        raise ToolError("The old string and new string are the same. No changes made.")
    file = Path(file_path)
    if not file.exists() or not file.is_file():
        raise ToolError(
            f"The file {file_path} does not exist or is not a file. Use glob or grep to search for the right path."
        )
    if not old_string:
        raise ToolError("The old string to be replaced cannot be empty.")
    content = file.read_text()
    if old_string not in content:
        raise ToolError(
            f"The string old_string was not found in the file {file_path}. Please ensure the string is correct."
        )
    if content.count(old_string) > 1:
        raise ToolError(
            f"The string old_string was found multiple times in the file {file_path}. Please ensure it is unique. Include more surrounding context or use a more specific string to replace."
        )
    new_content = content.replace(old_string, new_string)
    file.write_text(new_content)
    diff = difflib.unified_diff(
        content.splitlines(),
        new_content.splitlines(),
        fromfile=f"{file_path} (before)",
        tofile=f"{file_path} (after)",
        lineterm="",
    )
    return "\n".join(diff)
