import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import docling_lib.server
from docling_lib.server import app


def test_auth_enabled():
    # Test with API Key enabled
    with patch("docling_lib.server.API_KEY", "test-api-key"):
        client = TestClient(app)
        files = {"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")}

        # Missing API Key
        response = client.post("/convert/", files=files)
        assert response.status_code == 401
        assert "Invalid or missing API Key" in response.json()["detail"]

        # Wrong API Key
        response = client.post(
            "/convert/", files=files, headers={"X-API-Key": "wrong-key"}
        )
        assert response.status_code == 401

        # Correct API Key (we expect a different error or success, but not 401)
        with patch("docling_lib.server._validate_extension", return_value=".pdf"):
            with patch(
                "docling_lib.server._save_upload_temp", return_value=Path("dummy_path")
            ):
                with patch(
                    "docling_lib.server._create_output_dir",
                    return_value=("id", Path("out")),
                ):
                    with patch("docling_lib.server.run_in_threadpool") as mock_run:
                        # Mock success for process_pdf and path exists
                        mock_run.return_value = Path("result.md")
                        response = client.post(
                            "/convert/",
                            files=files,
                            headers={"X-API-Key": "test-api-key"},
                        )
                        assert response.status_code != 401


def test_auth_disabled():
    # Test with API Key disabled
    with patch("docling_lib.server.API_KEY", None):
        client = TestClient(app)
        files = {"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")}

        # No API Key required
        with patch("docling_lib.server._validate_extension", return_value=".pdf"):
            with patch(
                "docling_lib.server._save_upload_temp", return_value=Path("dummy_path")
            ):
                with patch(
                    "docling_lib.server._create_output_dir",
                    return_value=("id", Path("out")),
                ):
                    with patch("docling_lib.server.run_in_threadpool") as mock_run:
                        mock_run.return_value = Path("result.md")
                        response = client.post("/convert/", files=files)
                        assert response.status_code != 401


def test_rate_limiting():
    # Reset rate limit data
    docling_lib.server._rate_limit_data.clear()

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 2):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 60):
            client = TestClient(app)
            files = {"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")}

            with patch("docling_lib.server._validate_extension", return_value=".pdf"):
                with patch(
                    "docling_lib.server._save_upload_temp",
                    return_value=Path("dummy_path"),
                ):
                    with patch(
                        "docling_lib.server._create_output_dir",
                        return_value=("id", Path("out")),
                    ):
                        with patch("docling_lib.server.run_in_threadpool") as mock_run:
                            mock_run.return_value = Path("result.md")
                            # First request
                            response = client.post("/convert/", files=files)
                            assert response.status_code != 429

                            # Second request
                            response = client.post("/convert/", files=files)
                            assert response.status_code != 429

                            # Third request -> Rate limited
                            response = client.post("/convert/", files=files)
                            assert response.status_code == 429
                            assert "Too Many Requests" in response.json()["detail"]


def test_rate_limiting_window():
    # Reset rate limit data
    docling_lib.server._rate_limit_data.clear()

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 1):
            client = TestClient(app)
            files = {"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")}

            with patch("docling_lib.server._validate_extension", return_value=".pdf"):
                with patch(
                    "docling_lib.server._save_upload_temp",
                    return_value=Path("dummy_path"),
                ):
                    with patch(
                        "docling_lib.server._create_output_dir",
                        return_value=("id", Path("out")),
                    ):
                        with patch("docling_lib.server.run_in_threadpool") as mock_run:
                            mock_run.return_value = Path("result.md")
                            # First request
                            response = client.post("/convert/", files=files)
                            assert response.status_code != 429

                            # Immediate second request -> Rate limited
                            response = client.post("/convert/", files=files)
                            assert response.status_code == 429

                            # Wait for window to expire
                            time.sleep(1.1)

                            # Third request -> Success
                            response = client.post("/convert/", files=files)
                            assert response.status_code != 429
