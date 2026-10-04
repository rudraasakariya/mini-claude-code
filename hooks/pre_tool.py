from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from agent.state import Action, ToolName
from config.constants import ProtectedPathRules
from config.settings import ProtectedPathSettings
from hooks.policy import Policy, rule_matches


class PermissionDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass(frozen=True)
class PreToolDecision:
    decision: PermissionDecision
    rule: str | None = None


def check_protected_paths(
    action: Action, root_path: Path, settings: ProtectedPathSettings
) -> str | None:
    """Return the protection an edit would break, or None if the path is fine."""
    if action.tool is not ToolName.EDIT:
        return None  # only edit writes files; run is the sandbox's job

    # resolve the same way the edit tool does, so ../ and symlinks are followed
    full_path = (root_path / action.arguments.get("file_path", "")).resolve()
    if full_path.is_relative_to(settings.harness_root):
        return ProtectedPathRules.HARNESS
    for name in settings.protected_dir_names:
        if name in full_path.parts:
            return ProtectedPathRules.PROTECTED_DIR.format(name=name)
    return None


def pre_tool_decision(
    policy: Policy,
    action: Action,
    root_path: Path,
    protected_settings: ProtectedPathSettings,
) -> PreToolDecision:
    """Given a tool call, return whether it is allowed, denied, or should ask the user."""
    # protected paths come first, so no policy rule can switch them off
    protected = check_protected_paths(action, root_path, protected_settings)
    if protected is not None:
        return PreToolDecision(decision=PermissionDecision.DENY, rule=protected)
    for rule in policy.deny.get(action.tool, ()):
        if rule_matches(rule, action):
            return PreToolDecision(decision=PermissionDecision.DENY, rule=rule.text)
    for rule in policy.ask.get(action.tool, ()):
        if rule_matches(rule, action):
            return PreToolDecision(decision=PermissionDecision.ASK, rule=rule.text)
    return PreToolDecision(decision=PermissionDecision.ALLOW)
