from unittest.mock import patch

from fastapi.testclient import TestClient

import docling_lib.server
from docling_lib.server import app


def test_rate_limit_respects_x_forwarded_for():
    # Reset rate limit data
    docling_lib.server._rate_limit_data.clear()

    # Set a low rate limit for testing
    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 60):
            with patch("docling_lib.server.API_KEY", None):
                client = TestClient(app)

                # First request with X-Forwarded-For: 1.1.1.1
                response1 = client.get("/download/id1/file1.md", headers={"X-Forwarded-For": "1.1.1.1"})
                assert response1.status_code != 429

                # Second request with DIFFERENT X-Forwarded-For: 2.2.2.2
                # This should NOT be rate limited now because it's a different IP
                response2 = client.get("/download/id2/file2.md", headers={"X-Forwarded-For": "2.2.2.2"})
                assert response2.status_code != 429

                # Third request with SAME X-Forwarded-For: 1.1.1.1
                # This SHOULD be rate limited
                response3 = client.get("/download/id3/file3.md", headers={"X-Forwarded-For": "1.1.1.1"})
                assert response3.status_code == 429

def test_rate_limit_respects_x_real_ip():
    # Reset rate limit data
    docling_lib.server._rate_limit_data.clear()

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 60):
            with patch("docling_lib.server.API_KEY", None):
                client = TestClient(app)

                # First request with X-Real-IP: 3.3.3.3
                response1 = client.get("/download/id1/file1.md", headers={"X-Real-IP": "3.3.3.3"})
                assert response1.status_code != 429

                # Second request with DIFFERENT X-Real-IP: 4.4.4.4
                response2 = client.get("/download/id2/file2.md", headers={"X-Real-IP": "4.4.4.4"})
                assert response2.status_code != 429

def test_rate_limit_handles_multiple_x_forwarded_for():
    # Reset rate limit data
    docling_lib.server._rate_limit_data.clear()

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 60):
            with patch("docling_lib.server.API_KEY", None):
                client = TestClient(app)

                # X-Forwarded-For: client1, proxy1, proxy2
                response1 = client.get("/download/id1/file1.md", headers={"X-Forwarded-For": "10.0.0.1, 10.0.0.2, 10.0.0.3"})
                assert response1.status_code != 429

                # Same client IP (10.0.0.1) should be rate limited even if proxies change
                response2 = client.get("/download/id2/file2.md", headers={"X-Forwarded-For": "10.0.0.1, 192.168.1.1"})
                assert response2.status_code == 429
