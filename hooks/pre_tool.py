from dataclasses import dataclass
from enum import Enum

from agent.state import Action
from hooks.policy import Policy, rule_matches


class PermissionDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass(frozen=True)
class PreToolDecision:
    decision: PermissionDecision
    rule: str | None = None


def pre_tool_decision(policy: Policy, action: Action) -> PreToolDecision:
    """Given a tool call, return whether it is allowed, denied, or should ask the user."""
    for rule in policy.deny.get(action.tool, ()):
        if rule_matches(rule, action):
            return PreToolDecision(decision=PermissionDecision.DENY, rule=rule.text)
    for rule in policy.ask.get(action.tool, ()):
        if rule_matches(rule, action):
            return PreToolDecision(decision=PermissionDecision.ASK, rule=rule.text)
    return PreToolDecision(decision=PermissionDecision.ALLOW)
