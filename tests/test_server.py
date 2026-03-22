from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import docling_lib.server
from docling_lib.server import app

client = TestClient(app)

# Create test data directory if it doesn't exist
TEST_DATA_DIR = Path("tests/test_data")
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Create a small dummy docx for testing if it doesn't exist
DUMMY_DOCX = TEST_DATA_DIR / "test_document.docx"
if not DUMMY_DOCX.exists():
    # This is not a real DOCX but enough for mocking tests
    DUMMY_DOCX.write_text("dummy docx content")


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Docling Markdown Conversion Server"}


def test_convert_file_invalid_extension():
    files = {"file": ("test.txt", b"dummy content", "text/plain")}
    response = client.post("/convert/", files=files)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


@patch("docling_lib.server.process_pdf")
def test_convert_file(mock_process, tmp_path, monkeypatch):
    # Setup temporary directories for the test
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "output"
    upload_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(docling_lib.server, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(docling_lib.server, "OUTPUT_DIR", output_dir)

    # Path to the test document
    file_path = DUMMY_DOCX
    
    def side_effect(input_path, request_output_dir):
        # Create a dummy result file in the expected location
        res = request_output_dir / "processed_document.md"
        res.write_text("# Mocked Results")
        return res

    mock_process.side_effect = side_effect

    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        response = client.post("/convert/", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Conversion successful"
    assert data["markdown_file"] == "processed_document.md"
    assert "output_id" in data
    assert "download_url" in data

    # Verify the download URL works
    output_id = data["output_id"]
    download_res = client.get(f"/download/{output_id}/processed_document.md")
    assert download_res.status_code == 200
    assert download_res.text == "# Mocked Results"


@patch("docling_lib.server.process_pdf")
def test_convert_file_failure(mock_process, tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "output"
    upload_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(docling_lib.server, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(docling_lib.server, "OUTPUT_DIR", output_dir)

    mock_process.return_value = None  # Indicate failure

    file_path = DUMMY_DOCX
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        response = client.post("/convert/", files=files)

    assert response.status_code == 500
    assert "Conversion failed" in response.json()["detail"]


@patch("docling_lib.server.process_pdf")
def test_convert_file_exception(mock_process, tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "output"
    upload_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(docling_lib.server, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(docling_lib.server, "OUTPUT_DIR", output_dir)

    mock_process.side_effect = Exception("Unexpected error")

    file_path = DUMMY_DOCX
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        response = client.post("/convert/", files=files)

    assert response.status_code == 500
    # Match the actual error message from server.py
    assert "An internal error occurred during conversion." in response.json()["detail"]


def test_download_file_not_found():
    response = client.get("/download/nonexistent/file.md")
    assert response.status_code == 404
