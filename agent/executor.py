from typing import Callable

from agent.state import Action, ToolName
from config.settings import ToolSettings
from mcp_server.errors import ToolError
from mcp_server.tools.edit import edit_file
from mcp_server.tools.glob import glob
from mcp_server.tools.grep import grep
from mcp_server.tools.read import read_file
from mcp_server.tools.run import run

ERROR_PREFIX = "Error: "
TOOL_NOT_AVAILABLE = "Tool {tool} is not available yet."

TOOLS: dict[ToolName, Callable[..., str]] = {
    ToolName.READ: read_file,
    ToolName.GREP: grep,
    ToolName.RUN: run,
    ToolName.GLOB: glob,
    ToolName.EDIT: edit_file,
}


def execute_action(action: Action, settings: ToolSettings) -> str:
    tool_func = TOOLS.get(action.tool)
    if tool_func is None:
        return TOOL_NOT_AVAILABLE.format(tool=action.tool.value)

    limits = {
        ToolName.GREP: {"max_results": settings.max_grep_results},
        ToolName.READ: {"max_lines": settings.max_read_lines},
        ToolName.GLOB: {"max_results": settings.max_glob_results},
        ToolName.RUN: {"max_output_chars": settings.max_run_output_chars},
    }
    arguments = {**action.arguments, **limits.get(action.tool, {})}

    try:
        return tool_func(**arguments)
    except (ToolError, TypeError) as e:
        return f"{ERROR_PREFIX}{e}"
