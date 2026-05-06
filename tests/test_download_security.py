import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import docling_lib.server
from docling_lib.server import app

client = TestClient(app)

@pytest.fixture
def mock_output_dir(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(docling_lib.server, "OUTPUT_DIR", output_dir)
    return output_dir

def test_download_valid_request(mock_output_dir):
    # Valid request
    request_id = "abc123def456"
    filename = "processed.md"
    request_dir = mock_output_dir / request_id
    request_dir.mkdir()
    file_path = request_dir / filename
    file_path.write_text("content")

    response = client.get(f"/download/{request_id}/{filename}")
    assert response.status_code == 200
    assert response.text == "content"

def test_download_non_alphanumeric_request_id(mock_output_dir):
    # Non-alphanumeric request_id should be caught by our validation
    # Using characters that don't break the URL structure
    response = client.get("/download/id-with-dash/file.md")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid request parameters."

def test_download_request_id_with_dot(mock_output_dir):
    # request_id with dot
    response = client.get("/download/id.with.dot/file.md")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid request parameters."

def test_download_request_id_traversal_attempt(mock_output_dir):
    # Attempting traversal with '..'
    # Note: Many clients/servers normalize this to 404 before it hits our logic,
    # but our logic should catch it if it gets through.
    response = client.get("/download/../file.md")
    assert response.status_code in [400, 404]

def test_download_filename_with_path_separators(mock_output_dir):
    # Filename with path components (if it were possible to pass them)
    # Since the route is {request_id}/{filename}, extra slashes usually 404
    response = client.get("/download/validid/subdir/file.md")
    assert response.status_code in [400, 404]
