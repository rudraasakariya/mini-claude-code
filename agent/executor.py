import logging
from collections.abc import Callable
from pathlib import Path

from pydantic import ValidationError

from agent.state import Action, InvalidToolCall, ToolName
from config.constants import ExecutorMessages, LogMessages
from config.settings import ProtectedPathSettings, ToolSettings
from hooks.policy import Policy
from hooks.pre_tool import PermissionDecision, pre_tool_decision
from mcp_server.errors import ToolError
from mcp_server.schemas import ToolSpecification
from mcp_server.tools.edit import EDIT_TOOL_SPECIFICATION, edit_file
from mcp_server.tools.glob import GLOB_TOOL_SPECIFICATION, glob
from mcp_server.tools.grep import GREP_TOOL_SPECIFICATION, grep
from mcp_server.tools.read import READ_TOOL_SPECIFICATION, read_file
from mcp_server.tools.run import RUN_TOOL_SPECIFICATION, run

logger = logging.getLogger(__name__)


TOOLS: dict[ToolName, tuple[ToolSpecification, Callable[..., str]]] = {
    ToolName.READ: (READ_TOOL_SPECIFICATION, read_file),
    ToolName.GREP: (GREP_TOOL_SPECIFICATION, grep),
    ToolName.RUN: (RUN_TOOL_SPECIFICATION, run),
    ToolName.GLOB: (GLOB_TOOL_SPECIFICATION, glob),
    ToolName.EDIT: (EDIT_TOOL_SPECIFICATION, edit_file),
}


def execute_action(
    action: Action | InvalidToolCall,
    tool_settings: ToolSettings,
    root_path: Path,
    policy: Policy,
    protected_settings: ProtectedPathSettings,
) -> str:
    if isinstance(action, InvalidToolCall):
        available = ", ".join(tool.value for tool in TOOLS)
        message = ExecutorMessages.INVALID_TOOL_CALL.format(
            tool=action.name, available=available
        )
        return f"{ExecutorMessages.ERROR_PREFIX}{message}"

    decision = pre_tool_decision(policy, action, root_path, protected_settings)
    if decision.decision is not PermissionDecision.ALLOW:
        logger.warning(
            LogMessages.TOOL_BLOCKED,
            extra={"tool": action.tool.value, "rule": decision.rule},
        )
        return f"{ExecutorMessages.ERROR_PREFIX}{ExecutorMessages.TOOL_BLOCKED.format(tool=action.tool.value, rule=decision.rule)}"

    # parse_response only builds an Action for a tool in TOOLS
    specification, tool_function = TOOLS[action.tool]

    limits = {
        ToolName.GREP: {"max_results": tool_settings.max_grep_results},
        ToolName.READ: {"max_lines": tool_settings.max_read_lines},
        ToolName.GLOB: {"max_results": tool_settings.max_glob_results},
        ToolName.RUN: {
            "max_output_chars": tool_settings.max_run_output_chars,
            "max_timeout_seconds": tool_settings.max_timeout_seconds,
        },
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
    except Exception as e:
        logger.exception(
            LogMessages.TOOL_FAILED,
            extra={"tool": action.tool.value, "call_id": action.call_id},
        )
        return f"{ExecutorMessages.ERROR_PREFIX}{ExecutorMessages.TOOL_FAILED.format(tool=action.tool.value, error=type(e).__name__)}"
