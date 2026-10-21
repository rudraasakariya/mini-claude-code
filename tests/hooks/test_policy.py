import pytest

from agent.state import Action, ToolName
from hooks.errors import PolicyError
from hooks.policy import parse_rule, rule_matches


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


def run_action(command: str) -> Action:
    return Action(tool=ToolName.RUN, call_id="call", arguments={"command": command})


@pytest.mark.parametrize(
    ("rule_text", "command", "expected"),
    [
        ("run(git push *)", "git push origin main", True),
        ("run(git push *)", "git pull origin main", False),
        ("run(git push *)", "git push", False),  # "* " needs the space after push
        ("run(rm -rf *)", "rm -rf build", True),
    ],
)
def test_rule_matches_whole_command(rule_text, command, expected):
    assert rule_matches(parse_rule(rule_text), run_action(command)) is expected


def test_rule_ignores_calls_without_its_argument():
    rule = parse_rule("run(git push *)")
    action = Action(tool=ToolName.RUN, call_id="call", arguments={})
    assert rule_matches(rule, action) is False


@pytest.mark.xfail(
    reason="rules match the whole command; chaining hides it", strict=True
)
def test_rule_catches_chained_command():
    rule = parse_rule("run(git push *)")
    assert rule_matches(rule, run_action("cd repo && git push origin main"))
