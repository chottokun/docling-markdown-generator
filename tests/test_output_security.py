import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from docling_lib.converter import _validate_output_security

def test_validate_output_security_valid_relative(tmp_path, monkeypatch):
    """Verify that a simple relative path returns True."""
    monkeypatch.chdir(tmp_path)
    assert _validate_output_security(Path("output")) is True

def test_validate_output_security_valid_nested(tmp_path, monkeypatch):
    """Verify that a nested relative path returns True."""
    monkeypatch.chdir(tmp_path)
    assert _validate_output_security(Path("subdir/output")) is True

def test_validate_output_security_traversal(tmp_path, monkeypatch):
    """Verify that a path with .. that goes outside CWD returns False."""
    monkeypatch.chdir(tmp_path)
    # Path("../outside") resolved will be outside tmp_path
    assert _validate_output_security(Path("../outside")) is False

def test_validate_output_security_absolute_outside(tmp_path, monkeypatch):
    """Verify that an absolute path outside CWD returns False."""
    monkeypatch.chdir(tmp_path)
    outside_path = tmp_path.parent.resolve() / "outside_dir"
    assert _validate_output_security(outside_path) is False

def test_validate_output_security_absolute_inside(tmp_path, monkeypatch):
    """Verify that an absolute path inside CWD returns True."""
    monkeypatch.chdir(tmp_path)
    inside_path = (tmp_path / "inside_dir").resolve()
    assert _validate_output_security(inside_path) is True

def test_validate_output_security_exception(tmp_path, monkeypatch, caplog):
    """Verify handling of exceptions during path resolution."""
    monkeypatch.chdir(tmp_path)
    # We patch the specific Path class used in the module
    with patch("docling_lib.converter.Path.resolve", side_effect=RuntimeError("Simulated error")):
        with caplog.at_level(logging.ERROR):
            result = _validate_output_security(Path("output"))
            assert result is False
            assert "Security Error during path resolution: Simulated error" in caplog.text
