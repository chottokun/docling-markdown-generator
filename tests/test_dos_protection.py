from unittest.mock import patch

from fastapi.testclient import TestClient

import docling_lib.server
from docling_lib.server import app

client = TestClient(app)

def test_convert_file_size_limit_header():
    # Reset rate limit data
    docling_lib.server._rate_limit_data.clear()

    # Test size limit via Content-Length header
    files = {"file": ("test.pdf", b"dummy content", "application/pdf")}
    headers = {"Content-Length": str(100 * 1024 * 1024)} # 100MB
    response = client.post("/convert/", files=files, headers=headers)
    assert response.status_code == 413
    assert "Payload Too Large" in response.json()["detail"]

@patch("docling_lib.server._validate_extension", return_value=".pdf")
def test_convert_file_size_limit_read(mock_ext, tmp_path, monkeypatch):
    # Reset rate limit data to ensure this test doesn't hit it accidentally
    docling_lib.server._rate_limit_data.clear()

    # Test size limit via actual read loop
    # Set a very small limit for testing
    monkeypatch.setattr(docling_lib.server, "MAX_UPLOAD_SIZE", 10)
    monkeypatch.setattr(docling_lib.server, "UPLOAD_DIR", tmp_path)

    files = {"file": ("test.pdf", b"this is more than 10 bytes", "application/pdf")}
    response = client.post("/convert/", files=files)
    assert response.status_code == 413
    assert "Payload Too Large" in response.json()["detail"]
