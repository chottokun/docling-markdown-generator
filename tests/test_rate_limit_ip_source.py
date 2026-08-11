from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import docling_lib.server
from docling_lib.server import app


@pytest.fixture(autouse=True)
def override_api_key_auth():
    from docling_lib.server import api_key_auth
    app.dependency_overrides[api_key_auth] = lambda: None
    yield
    app.dependency_overrides.clear()


def test_rate_limit_respects_x_forwarded_for():
    # Reset rate limit data
    docling_lib.server._rate_limit_data.clear()

    # Set a low rate limit for testing
    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 60):
            with patch("docling_lib.server.API_KEY", None):
                with patch("docling_lib.server.TRUSTED_PROXIES", ["*"]):
                    client = TestClient(app)

                    # First request with X-Forwarded-For: 1.1.1.1
                    response1 = client.get(
                        "/download/id1/file1.md", headers={"X-Forwarded-For": "1.1.1.1"}
                    )
                    assert response1.status_code != 429

                    # Second request with DIFFERENT X-Forwarded-For: 2.2.2.2
                    # This should NOT be rate limited now because it's a different IP
                    response2 = client.get(
                        "/download/id2/file2.md", headers={"X-Forwarded-For": "2.2.2.2"}
                    )
                    assert response2.status_code != 429

                    # Third request with SAME X-Forwarded-For: 1.1.1.1
                    # This SHOULD be rate limited
                    response3 = client.get(
                        "/download/id3/file3.md", headers={"X-Forwarded-For": "1.1.1.1"}
                    )
                    assert response3.status_code == 429


def test_rate_limit_respects_x_real_ip():
    # Reset rate limit data
    docling_lib.server._rate_limit_data.clear()

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 60):
            with patch("docling_lib.server.API_KEY", None):
                with patch("docling_lib.server.TRUSTED_PROXIES", ["*"]):
                    client = TestClient(app)

                    # First request with X-Real-IP: 3.3.3.3
                    response1 = client.get(
                        "/download/id1/file1.md", headers={"X-Real-IP": "3.3.3.3"}
                    )
                    assert response1.status_code != 429

                    # Second request with DIFFERENT X-Real-IP: 4.4.4.4
                    response2 = client.get(
                        "/download/id2/file2.md", headers={"X-Real-IP": "4.4.4.4"}
                    )
                    assert response2.status_code != 429


def test_rate_limit_handles_multiple_x_forwarded_for():
    # Reset rate limit data
    docling_lib.server._rate_limit_data.clear()

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 60):
            with patch("docling_lib.server.API_KEY", None):
                with patch("docling_lib.server.TRUSTED_PROXIES", ["*"]):
                    client = TestClient(app)

                    # X-Forwarded-For: client1, proxy1, proxy2
                    response1 = client.get(
                        "/download/id1/file1.md",
                        headers={"X-Forwarded-For": "10.0.0.1, 10.0.0.2, 10.0.0.3"},
                    )
                    assert response1.status_code != 429

                    # Same client IP (10.0.0.1) should be rate limited even if proxies change
                    response2 = client.get(
                        "/download/id2/file2.md",
                        headers={"X-Forwarded-For": "10.0.0.1, 192.168.1.1"},
                    )
                    assert response2.status_code == 429


def test_rate_limit_ignores_headers_if_proxy_not_trusted():
    # Reset rate limit data
    docling_lib.server._rate_limit_data.clear()

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 60):
            with patch("docling_lib.server.API_KEY", None):
                # When TRUSTED_PROXIES is empty, the server only trusts the connection IP (testclient).
                with patch("docling_lib.server.TRUSTED_PROXIES", []):
                    client = TestClient(app)

                    # First request with X-Forwarded-For: 1.1.1.1
                    response1 = client.get(
                        "/download/id1/file1.md", headers={"X-Forwarded-For": "1.1.1.1"}
                    )
                    assert response1.status_code != 429

                    # Second request with X-Forwarded-For: 2.2.2.2.
                    # Since the headers are ignored, the client IP resolves to "testclient" for both requests.
                    # Therefore, this second request should trigger rate limit (429).
                    response2 = client.get(
                        "/download/id2/file2.md", headers={"X-Forwarded-For": "2.2.2.2"}
                    )
                    assert response2.status_code == 429


def test_rate_limit_trusts_specific_cidr_proxies():
    # Reset rate limit data
    docling_lib.server._rate_limit_data.clear()

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 60):
            with patch("docling_lib.server.API_KEY", None):
                # We mock TRUSTED_PROXIES to trust '127.0.0.1/24' and 'testclient'
                with patch(
                    "docling_lib.server.TRUSTED_PROXIES", ["127.0.0.1/24", "testclient"]
                ):
                    client = TestClient(app)

                    # Since 'testclient' is trusted (it matches literally or is in the list), headers are honored.
                    response1 = client.get(
                        "/download/id1/file1.md", headers={"X-Forwarded-For": "1.1.1.1"}
                    )
                    assert response1.status_code != 429

                    response2 = client.get(
                        "/download/id2/file2.md", headers={"X-Forwarded-For": "2.2.2.2"}
                    )
                    assert response2.status_code != 429


def test_rate_limit_ignores_invalid_ip_format_in_trusted_proxies():
    # Reset rate limit data
    docling_lib.server._rate_limit_data.clear()

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 60):
            with patch("docling_lib.server.API_KEY", None):
                # 'invalid_cidr_format' in trusted proxies should not crash the server and 'testclient' should still work
                with patch(
                    "docling_lib.server.TRUSTED_PROXIES",
                    ["invalid_cidr_format", "testclient"],
                ):
                    client = TestClient(app)

                    response1 = client.get(
                        "/download/id1/file1.md", headers={"X-Forwarded-For": "1.1.1.1"}
                    )
                    assert response1.status_code != 429

                    response2 = client.get(
                        "/download/id2/file2.md", headers={"X-Forwarded-For": "2.2.2.2"}
                    )
                    assert response2.status_code != 429


def test_rate_limit_trusted_proxies_ipv6():
    # Reset rate limit data
    docling_lib.server._rate_limit_data.clear()

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 60):
            with patch("docling_lib.server.API_KEY", None):
                # IPv6 range in trusted proxies
                with patch(
                    "docling_lib.server.TRUSTED_PROXIES",
                    ["2001:db8::/32", "testclient"],
                ):
                    client = TestClient(app)

                    # Headers honored since 'testclient' is in the trusted proxy list
                    response1 = client.get(
                        "/download/id1/file1.md",
                        headers={"X-Forwarded-For": "2001:db8::1"},
                    )
                    assert response1.status_code != 429

                    response2 = client.get(
                        "/download/id2/file2.md",
                        headers={"X-Forwarded-For": "2001:db8::2"},
                    )
                    assert response2.status_code != 429


def test_rate_limit_secure_proxy_chain_traversal():
    # Reset rate limit data
    docling_lib.server._rate_limit_data.clear()

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 60):
            with patch("docling_lib.server.API_KEY", None):
                # Let's trust '192.168.1.0/24' and 'testclient' but NOT others
                with patch(
                    "docling_lib.server.TRUSTED_PROXIES",
                    ["192.168.1.0/24", "testclient"],
                ):
                    client = TestClient(app)

                    # Chain: 1.1.1.1 (untrusted), 192.168.1.5 (trusted), 192.168.1.10 (trusted)
                    # Connection IP is 'testclient' (trusted)
                    # Since we traverse backwards (right to left):
                    # - 192.168.1.10 is trusted
                    # - 192.168.1.5 is trusted
                    # - 1.1.1.1 is untrusted -> should resolve to 1.1.1.1
                    response1 = client.get(
                        "/download/id1/file1.md",
                        headers={"X-Forwarded-For": "1.1.1.1, 192.168.1.5, 192.168.1.10"},
                    )
                    assert response1.status_code != 429

                    # If client tries to spoof with a malicious untrusted prefix:
                    # Chain: 2.2.2.2 (untrusted-spoofed), 9.9.9.9 (untrusted-original), 192.168.1.10 (trusted)
                    # Traverse right to left:
                    # - 192.168.1.10 is trusted
                    # - 9.9.9.9 is untrusted -> should stop here and resolve client IP as 9.9.9.9 (and ignore 2.2.2.2)
                    # Let's make a request from 9.9.9.9 (via spoofed header)
                    response2 = client.get(
                        "/download/id2/file2.md",
                        headers={"X-Forwarded-For": "2.2.2.2, 9.9.9.9, 192.168.1.10"},
                    )
                    assert response2.status_code != 429

                    # Now send another request with a different leftmost IP but same untrusted intermediary 9.9.9.9
                    # Chain: 3.3.3.3 (untrusted-spoofed), 9.9.9.9 (untrusted-original), 192.168.1.10 (trusted)
                    # Since the resolved IP is still 9.9.9.9, it should be rate limited (429)!
                    response3 = client.get(
                        "/download/id3/file3.md",
                        headers={"X-Forwarded-For": "3.3.3.3, 9.9.9.9, 192.168.1.10"},
                    )
                    assert response3.status_code == 429


def test_rate_limit_secure_proxy_chain_all_trusted():
    # Reset rate limit data
    docling_lib.server._rate_limit_data.clear()

    with patch("docling_lib.server.RATE_LIMIT_REQUESTS", 1):
        with patch("docling_lib.server.RATE_LIMIT_WINDOW", 60):
            with patch("docling_lib.server.API_KEY", None):
                # Trust everyone/wildcard
                with patch("docling_lib.server.TRUSTED_PROXIES", ["*"]):
                    client = TestClient(app)

                    # Chain has only trusted proxies, should default to the leftmost one.
                    response1 = client.get(
                        "/download/id1/file1.md",
                        headers={"X-Forwarded-For": "1.1.1.1, 2.2.2.2, 3.3.3.3"},
                    )
                    assert response1.status_code != 429

                    # Same leftmost IP, should rate limit.
                    response2 = client.get(
                        "/download/id2/file2.md",
                        headers={"X-Forwarded-For": "1.1.1.1, 4.4.4.4, 5.5.5.5"},
                    )
                    assert response2.status_code == 429
