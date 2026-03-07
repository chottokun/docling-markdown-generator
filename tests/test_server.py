import pytest
from fastapi.testclient import TestClient
from pathlib import Path
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


@pytest.mark.skip(reason="Requires real conversion or heavy mocking of DocumentConverter")
def test_convert_file():
    # Path to the test document
    file_path = DUMMY_DOCX
    
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        response = client.post("/convert/", files=files)
    
    assert response.status_code == 200
    assert "Conversion successful" in response.json()["message"]
    assert "markdown_file" in response.json()


def test_download_file_not_found():
    response = client.get("/download/nonexistent/file.md")
    assert response.status_code == 404
