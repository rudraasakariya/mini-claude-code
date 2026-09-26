import subprocess
from mcp_server.errors import ToolError
from mcp_server.schemas import ToolSpec
from agent.state import ToolName
from pydantic import BaseModel, Field

OMITTED_MARKER = "\n[... {omitted} characters omitted ...]\n"


class RunArgs(BaseModel):
    command: str = Field(description="The shell command to run.")
    timeout: int = Field(description="The maximum time in seconds to allow the command to run.")
    description: str = Field(default="", description="A description of what the command does. You can use this to provide context for the command, but it is not executed. And you should always try to provide this")

RUN_SPEC = ToolSpec(
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
    return text[:half] + OMITTED_MARKER.format(omitted=omitted) + text[-half:]

def run(command: str, timeout: int, description: str = "", *, max_output_chars: int) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise ToolError(f"Command timed out after {timeout} seconds.") from e

    output = (
        f"exit code: {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return truncate_middle(output, max_output_chars)