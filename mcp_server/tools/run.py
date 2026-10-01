import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from agent.state import ToolName
from config.constants import ToolMessages
from mcp_server.errors import ToolError
from mcp_server.schemas import ToolSpecification


class RunArgs(BaseModel):
    command: str = Field(description="The shell command to run.")
    timeout: int = Field(description="The maximum time in seconds to allow the command to run.")
    description: str = Field(
        default="",
        description="A short note for the user about what the command does. It is not executed. Always provide it.",
    )


RUN_TOOL_SPECIFICATION = ToolSpecification(
    name=ToolName.RUN,
    description=(
        "Run a shell command and return its exit code, stdout and stderr. "
        "Use it to run tests or other commands that read, grep, glob and edit cannot do. "
        "Commands cannot ask for input, so use non-interactive flags. "
        "Output is capped, so filter or narrow the command if the result says it was truncated. "
        "Set description to a short note for the user about what the command is for."
    ),
    args=RunArgs,
)


def truncate_middle(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    half = max_length // 2
    omitted = len(text) - 2 * half
    return text[:half] + ToolMessages.OUTPUT_OMITTED.format(omitted=omitted) + text[-half:]


def run(command: str, timeout: int, description: str = "", *, root_path: Path, max_output_chars: int) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=root_path,
            shell=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise ToolError(ToolMessages.COMMAND_TIMEOUT.format(timeout=timeout)) from e

    output = ToolMessages.COMMAND_OUTPUT.format(
        exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr
    )
    return truncate_middle(output, max_output_chars)
