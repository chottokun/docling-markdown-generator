import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from pathlib import Path
from fastapi import HTTPException
import docling_lib.server
from docling_lib.server import app, download_file

client = TestClient(app)

def test_download_file_oserror_in_resolution():
    """
    Test that download_file returns 400 when an OSError occurs during path resolution.
    """
    with patch("docling_lib.server.Path.resolve") as mock_resolve:
        mock_resolve.side_effect = OSError("Mocked OS error")
        response = client.get("/download/validid/file.md")
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid request parameters."

def test_download_file_invalid_request_id():
    """
    Test that download_file returns 400 for non-alphanumeric request_id (with forbidden chars).
    """
    response = client.get("/download/invalid_id!/file.md")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid request parameters."

@pytest.mark.asyncio
async def test_download_file_invalid_filename():
    """
    Test that download_file returns 400 for filename with path components.
    Note: TestClient normalizes ../ so we test the handler logic directly.
    """
    with pytest.raises(HTTPException) as excinfo:
        await download_file("validid", "../traversal.md")

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Invalid request parameters."

def test_download_file_unauthorized_traversal(tmp_path, monkeypatch):
    """
    Test that download_file returns 404 and logs a warning when path traversal is detected
    (i.e., file_path is not relative to safe_dir or resolved_output_dir).
    """
    monkeypatch.setattr(docling_lib.server, "OUTPUT_DIR", tmp_path)

    # We need to mock is_relative_to because it's hard to get Path.resolve to return
    # something outside tmp_path without actually escaping.
    with patch("docling_lib.server.Path.is_relative_to") as mock_rel:
        # First call for in_output, second for in_safe
        mock_rel.side_effect = [True, False]

        response = client.get("/download/validid/file.md")
        assert response.status_code == 404
        assert response.json()["detail"] == "File not found."

def test_download_file_not_a_file(tmp_path, monkeypatch):
    """
    Test that download_file returns 404 when the path exists but is not a file (e.g., a directory).
    """
    monkeypatch.setattr(docling_lib.server, "OUTPUT_DIR", tmp_path)
    request_id = "testid"
    dir_name = "not_a_file"

    request_dir = tmp_path / request_id
    request_dir.mkdir(parents=True)
    subdir = request_dir / dir_name
    subdir.mkdir()

    response = client.get(f"/download/{request_id}/{dir_name}")
    assert response.status_code == 404
    assert response.json()["detail"] == "File not found."
