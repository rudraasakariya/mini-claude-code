from config.constants import ToolMessages
from mcp_server.tools.run import truncate_middle


def test_short_text_is_unchanged():
    text = "hello"
    result = truncate_middle(text, 10)
    assert result == text


def test_text_at_limit_is_unchanged():
    text = "a" * 10  # exactly max_length: the <= edge case
    result = truncate_middle(text, 10)
    assert result == text


def test_long_text_keeps_head_and_tail():
    text = "a" * 50 + "b" * 50  # different ends, so we can tell head from tail
    result = truncate_middle(text, 10)

    # half = 10 // 2 = 5 kept from each end; 100 - 10 = 90 dropped
    marker = ToolMessages.OUTPUT_OMITTED.format(omitted=90)
    assert result == "aaaaa" + marker + "bbbbb"
