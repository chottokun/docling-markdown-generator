import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import UploadFile, HTTPException
from pathlib import Path
import docling_lib.server
from docling_lib.server import _save_upload_temp

@pytest.mark.asyncio
async def test_save_upload_temp_cleanup_on_exception(tmp_path, monkeypatch):
    """
    Verify that temporary files are cleaned up when an exception occurs during
    the upload saving process (e.g., a read error).
    """
    # Setup temporary UPLOAD_DIR
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(docling_lib.server, "UPLOAD_DIR", upload_dir)

    # Mock UploadFile to raise an exception during read
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(side_effect=Exception("Read error"))

    # The call should propagate the exception
    with pytest.raises(Exception, match="Read error"):
        await _save_upload_temp(mock_file, ".pdf")

    # Verify that UPLOAD_DIR is empty (file was unlinked)
    files_remaining = list(upload_dir.iterdir())
    assert len(files_remaining) == 0, f"Temporary files were not cleaned up: {files_remaining}"
