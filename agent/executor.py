from typing import Callable

from agent.state import Action, ToolName
from config.settings import ToolSettings
from mcp_server.errors import ToolError
from mcp_server.tools.edit import edit_file
from mcp_server.tools.glob import glob
from mcp_server.tools.grep import grep
from mcp_server.tools.read import read_file
from mcp_server.tools.run import run
from mcp_server.schemas import ToolSpec
from mcp_server.tools.edit import EDIT_SPEC
from mcp_server.tools.glob import GLOB_SPEC
from mcp_server.tools.grep import GREP_SPEC
from mcp_server.tools.read import READ_SPEC
from mcp_server.tools.run import RUN_SPEC
from pydantic import ValidationError

ERROR_PREFIX = "Error: "
TOOL_NOT_AVAILABLE = "Tool {tool} is not available yet."

TOOLS: dict[ToolName, tuple[ToolSpec, Callable[..., str]]] = {
    ToolName.READ: (READ_SPEC, read_file),
    ToolName.GREP: (GREP_SPEC, grep),
    ToolName.RUN: (RUN_SPEC, run),
    ToolName.GLOB: (GLOB_SPEC, glob),
    ToolName.EDIT: (EDIT_SPEC, edit_file),
}


def execute_action(action: Action, settings: ToolSettings) -> str:
    entry = TOOLS.get(action.tool)
    if entry is None:
        return TOOL_NOT_AVAILABLE.format(tool=action.tool.value)
    
    spec , tool_func = entry

    limits = {
        ToolName.GREP: {"max_results": settings.max_grep_results},
        ToolName.READ: {"max_lines": settings.max_read_lines},
        ToolName.GLOB: {"max_results": settings.max_glob_results},
        ToolName.RUN: {"max_output_chars": settings.max_run_output_chars},
    }

    try:
        validated_args = spec.args(**action.arguments)
        return tool_func(**validated_args.model_dump(), **limits.get(action.tool, {}))
    except (ValidationError , ToolError) as e:
        return f"{ERROR_PREFIX}{e}"
