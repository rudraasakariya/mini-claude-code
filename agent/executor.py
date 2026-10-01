from collections.abc import Callable
from pathlib import Path

from pydantic import ValidationError

from agent.state import Action, ToolName
from config.constants import ExecutorMessages
from config.settings import ToolSettings
from mcp_server.errors import ToolError
from mcp_server.schemas import ToolSpecification
from mcp_server.tools.edit import EDIT_TOOL_SPECIFICATION, edit_file
from mcp_server.tools.glob import GLOB_TOOL_SPECIFICATION, glob
from mcp_server.tools.grep import GREP_TOOL_SPECIFICATION, grep
from mcp_server.tools.read import READ_TOOL_SPECIFICATION, read_file
from mcp_server.tools.run import RUN_TOOL_SPECIFICATION, run

TOOLS: dict[ToolName, tuple[ToolSpecification, Callable[..., str]]] = {
    ToolName.READ: (READ_TOOL_SPECIFICATION, read_file),
    ToolName.GREP: (GREP_TOOL_SPECIFICATION, grep),
    ToolName.RUN: (RUN_TOOL_SPECIFICATION, run),
    ToolName.GLOB: (GLOB_TOOL_SPECIFICATION, glob),
    ToolName.EDIT: (EDIT_TOOL_SPECIFICATION, edit_file),
}


def execute_action(action: Action, settings: ToolSettings, root_path: Path) -> str:
    entry = TOOLS.get(action.tool)
    if entry is None:
        return ExecutorMessages.TOOL_NOT_AVAILABLE.format(tool=action.tool.value)

    specification, tool_function = entry

    limits = {
        ToolName.GREP: {"max_results": settings.max_grep_results},
        ToolName.READ: {"max_lines": settings.max_read_lines},
        ToolName.GLOB: {"max_results": settings.max_glob_results},
        ToolName.RUN: {"max_output_chars": settings.max_run_output_chars},
    }

    try:
        validated_args = specification.args(**action.arguments)
        return tool_function(
            **validated_args.model_dump(),
            **limits.get(action.tool, {}),
            root_path=root_path,
        )
    except (ValidationError, ToolError) as e:
        return f"{ExecutorMessages.ERROR_PREFIX}{e}"
