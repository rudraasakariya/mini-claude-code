import re
from dataclasses import dataclass
from fnmatch import fnmatchcase

from pydantic import BaseModel, ConfigDict, ValidationError

from agent.state import Action, ToolName
from config.constants import PolicyFileMessages, PolicyFormat, PolicyMessages
from config.settings import PolicySettings
from hooks.errors import PolicyError

RULE_ARGUMENT: dict[ToolName, str] = {
    ToolName.RUN: "command",
    ToolName.READ: "file_path",
    ToolName.EDIT: "file_path",
    ToolName.GREP: "path",
    ToolName.GLOB: "path",
}


@dataclass(frozen=True)
class Rule:
    tool: ToolName
    pattern: str
    text: str  # the rule as written, kept so logs can name the rule that fired


def parse_rule(text: str) -> Rule:
    """Turn "run(git push *)" into Rule(tool=RUN, pattern="git push *")."""
    match = re.fullmatch(PolicyFormat.RULE_REGEX, text.strip())
    if match is None:
        raise PolicyError(PolicyMessages.INVALID_RULE.format(rule=text))

    tool_name, pattern = match.groups()
    try:
        tool = ToolName(tool_name)
    except ValueError as e:
        known = ", ".join(tool.value for tool in ToolName)
        raise PolicyError(
            PolicyMessages.UNKNOWN_TOOL.format(rule=text, tool=tool_name, known=known)
        ) from e
    return Rule(tool=tool, pattern=pattern, text=text)


def rule_matches(rule: Rule, action: Action) -> bool:
    value = action.arguments.get(RULE_ARGUMENT[action.tool])
    return isinstance(value, str) and fnmatchcase(value, rule.pattern)


class PolicyFile(BaseModel):
    """The shape policy.json must have; unknown keys (typos) are rejected."""

    model_config = ConfigDict(extra="forbid")

    deny: list[str] = []
    ask: list[str] = []


@dataclass(frozen=True)
class Policy:
    # rules grouped by tool, so a call is only checked against its own tool's rules
    deny: dict[ToolName, tuple[Rule, ...]]
    ask: dict[ToolName, tuple[Rule, ...]]


def group_by_tool(rules: list[Rule]) -> dict[ToolName, tuple[Rule, ...]]:
    grouped: dict[ToolName, list[Rule]] = {}
    for rule in rules:
        grouped.setdefault(rule.tool, []).append(rule)
    return {tool: tuple(tool_rules) for tool, tool_rules in grouped.items()}


def load_policy(settings: PolicySettings) -> Policy:
    """Read policy.json once at startup; any problem fails loudly."""
    try:
        raw = settings.path.read_text()
    except FileNotFoundError as e:
        raise PolicyError(
            PolicyFileMessages.NOT_FOUND.format(path=settings.path)
        ) from e
    try:
        policy_file = PolicyFile.model_validate_json(raw)
    except ValidationError as e:
        raise PolicyError(
            PolicyFileMessages.INVALID.format(path=settings.path, error=e)
        ) from e
    return Policy(
        deny=group_by_tool([parse_rule(text) for text in policy_file.deny]),
        ask=group_by_tool([parse_rule(text) for text in policy_file.ask]),
    )
