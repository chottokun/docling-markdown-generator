import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from unittest.mock import patch, MagicMock
import shutil
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
def test_convert_file_success(mock_process_pdf, tmp_path, monkeypatch):
    """
    Test successful file conversion by mocking process_pdf.
    """
    # Redirect OUTPUT_DIR to a temporary directory for the test
    monkeypatch.setattr(docling_lib.server, "OUTPUT_DIR", tmp_path)

    # Mock behavior of process_pdf
    def side_effect(input_path, output_dir, **kwargs):
        # Create a dummy markdown file in the output_dir
        md_file = output_dir / "processed_document.md"
        md_file.write_text("# Dummy Content")
        return md_file

    mock_process_pdf.side_effect = side_effect

    # Path to the test document
    file_path = DUMMY_DOCX
    
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        response = client.post("/convert/", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Conversion successful"
    assert data["markdown_file"] == "processed_document.md"
    assert "output_id" in data
    assert "download_url" in data

    # Verify process_pdf was called with the correct temporary output directory
    assert mock_process_pdf.called
    args, kwargs = mock_process_pdf.call_args
    # The second positional argument is request_output_dir
    assert str(args[1]).startswith(str(tmp_path))


@patch("docling_lib.server.process_pdf")
def test_convert_file_failure(mock_process_pdf):
    """
    Test case where process_pdf returns None (failure).
    """
    mock_process_pdf.return_value = None

    file_path = DUMMY_DOCX
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        response = client.post("/convert/", files=files)

    assert response.status_code == 500
    assert "Conversion failed" in response.json()["detail"]


@patch("docling_lib.server.process_pdf")
def test_convert_file_exception(mock_process_pdf):
    """
    Test case where process_pdf raises an exception.
    """
    mock_process_pdf.side_effect = Exception("Internal processing error")

    file_path = DUMMY_DOCX
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        response = client.post("/convert/", files=files)

    assert response.status_code == 500
    assert "Internal processing error" in response.json()["detail"]


def test_download_file_not_found():
    response = client.get("/download/nonexistent/file.md")
    assert response.status_code == 404
