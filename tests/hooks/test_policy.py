import pytest

from agent.state import ToolName
from hooks.errors import PolicyError
from hooks.policy import parse_rule


@pytest.mark.parametrize(
    ("text", "expected_tool", "expected_pattern"),
    [
        ("run(git push *)", ToolName.RUN, "git push *"),
        ("edit(*.env)", ToolName.EDIT, "*.env"),
        (" run(ls) ", ToolName.RUN, "ls"),
        ("run(echo (hi))", ToolName.RUN, "echo (hi)"),
    ],
)
def test_parse_rule_splits_tool_and_pattern(text, expected_tool, expected_pattern):
    rule = parse_rule(text)
    assert rule.tool == expected_tool
    assert rule.pattern == expected_pattern


@pytest.mark.parametrize(
    "text",
    [
        "(*.env)",  # no tool name
        "call(git push *)",  # unknown tool
        "git push",  # no parentheses
        "",  # empty
    ],
)
def test_parse_rule_rejects_bad_rules(text):
    with pytest.raises(PolicyError):
        parse_rule(text)
