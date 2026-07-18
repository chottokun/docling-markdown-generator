from pathlib import Path
from unittest.mock import MagicMock

import pytest

from docling_lib.server import _cleanup_temp_file


@pytest.mark.asyncio
async def test_cleanup_temp_file_none():
    """Verify that _cleanup_temp_file handles None without error."""
    await _cleanup_temp_file(None)


@pytest.mark.asyncio
async def test_cleanup_temp_file_exists(tmp_path):
    """Verify that _cleanup_temp_file deletes the file if it exists."""
    test_file = tmp_path / "test_cleanup.txt"
    test_file.write_text("content")
    assert test_file.exists()

    await _cleanup_temp_file(test_file)

    assert not test_file.exists()


@pytest.mark.asyncio
async def test_cleanup_temp_file_not_exists():
    """Verify that _cleanup_temp_file attempts to unlink even if the file does not exist."""
    mock_path = MagicMock(spec=Path)

    await _cleanup_temp_file(mock_path)

    mock_path.unlink.assert_called_once_with(missing_ok=True)


@pytest.mark.asyncio
async def test_cleanup_temp_file_unlink_called():
    """Verify that _cleanup_temp_file calls unlink with missing_ok=True."""
    mock_path = MagicMock(spec=Path)

    await _cleanup_temp_file(mock_path)

    mock_path.unlink.assert_called_once_with(missing_ok=True)
