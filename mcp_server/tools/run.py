import subprocess
from mcp_server.errors import ToolError

OMITTED_MARKER = "\n[... {omitted} characters omitted ...]\n"

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