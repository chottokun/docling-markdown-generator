import pytest
from docling_lib.utils import sanitize_log_message

def test_sanitize_log_message_normal():
    assert sanitize_log_message("hello world") == "hello world"

def test_sanitize_log_message_newline():
    assert sanitize_log_message("hello\nworld") == "hello world"

def test_sanitize_log_message_carriage_return():
    assert sanitize_log_message("hello\rworld") == "hello world"

def test_sanitize_log_message_mixed():
    assert sanitize_log_message("hello\r\nworld\n") == "hello  world "

def test_sanitize_log_message_non_string():
    assert sanitize_log_message(123) == "123"
    assert sanitize_log_message(None) == "None"

def test_sanitize_log_message_empty():
    assert sanitize_log_message("") == ""

def test_sanitize_log_message_multiple_newlines():
    assert sanitize_log_message("\n\n\n") == "   "
