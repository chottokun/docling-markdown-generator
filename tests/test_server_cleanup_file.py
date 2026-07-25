import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from docling_lib.server import cleanup_file


def test_cleanup_file_success(tmp_path, caplog):
    """Verify happy path: an existing file within CWD is successfully deleted."""
    # Create a temporary file in the current workspace (CWD/tmp_path)
    test_file = tmp_path / "test_to_delete.txt"
    test_file.write_text("dummy")
    assert test_file.exists()

    # To ensure it is relative to CWD, let's patch Path.cwd to return tmp_path
    with patch.object(Path, "cwd", return_value=tmp_path):
        with caplog.at_level(logging.DEBUG):
            cleanup_file(test_file)

    assert not test_file.exists()
    assert "Successfully cleaned up file" in caplog.text


def test_cleanup_file_non_existent(tmp_path):
    """Verify that a non-existent file path inside CWD returns without error and does not crash."""
    test_file = tmp_path / "does_not_exist.txt"
    assert not test_file.exists()

    with patch.object(Path, "cwd", return_value=tmp_path):
        cleanup_file(test_file)

    assert not test_file.exists()


def test_cleanup_file_traversal(tmp_path, caplog):
    """Verify that a file path pointing outside CWD triggers security error and returns early."""
    # Suppose CWD is tmp_path / "app", and file_path is tmp_path / "outside.txt"
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret")

    with patch.object(Path, "cwd", return_value=app_dir):
        with caplog.at_level(logging.ERROR):
            cleanup_file(outside_file)

    # File should NOT be deleted
    assert outside_file.exists()
    assert "Security Error: Traversal detected during cleanup" in caplog.text


def test_cleanup_file_os_error(tmp_path, caplog, monkeypatch):
    """Verify that OSError / PermissionError is caught and logged."""
    test_file = tmp_path / "test_os_error.txt"
    test_file.write_text("content")

    def mock_exists(self):
        raise PermissionError("Simulated permission error")

    # Use monkeypatch to patch Path.exists to raise PermissionError
    monkeypatch.setattr(Path, "exists", mock_exists)

    with patch.object(Path, "cwd", return_value=tmp_path):
        with caplog.at_level(logging.ERROR):
            cleanup_file(test_file)

    assert "Failed to delete file" in caplog.text
    assert "Simulated permission error" in caplog.text


def test_cleanup_file_unexpected_exception(tmp_path, caplog, monkeypatch):
    """Verify that any unexpected exception during path resolution is caught and logged."""
    test_file = tmp_path / "test_unexpected.txt"

    def mock_resolve(self, strict=False):
        raise ValueError("Simulated unexpected exception")

    # Use monkeypatch to patch Path.resolve to raise a generic Exception
    monkeypatch.setattr(Path, "resolve", mock_resolve)

    with patch.object(Path, "cwd", return_value=tmp_path):
        with caplog.at_level(logging.ERROR):
            cleanup_file(test_file)

    assert "Unexpected error during cleanup of file" in caplog.text
    assert "Simulated unexpected exception" in caplog.text
