import pytest

from docling_lib.utils import parse_math_block_newline, sanitize_log_message


@pytest.mark.parametrize(
    "input_message, expected_output",
    [
        ("hello world", "hello world"),
        ("hello\nworld", "hello world"),
        ("hello\rworld", "hello world"),
        ("hello\r\nworld\n", "hello  world "),
        (123, "123"),
        (None, "None"),
        ("", ""),
        ("\n\n\n", "   "),
    ],
)
def test_sanitize_log_message(input_message, expected_output):
    assert sanitize_log_message(input_message) == expected_output


@pytest.mark.parametrize(
    "input_val, expected_output",
    [
        ("auto", "auto"),
        ("AUTO", "auto"),
        ("  Auto  ", "auto"),
        ("true", True),
        ("TRUE", True),
        ("  True ", True),
        ("false", False),
        ("FALSE", False),
        (" False ", False),
        (True, True),
        (False, False),
        ("invalid", "auto"),
        (None, "auto"),
        (123, "auto"),
    ],
)
def test_parse_math_block_newline(input_val, expected_output):
    assert parse_math_block_newline(input_val) == expected_output
