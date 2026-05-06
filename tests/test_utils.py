import pytest
from docling_lib.utils import sanitize_log_message

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
