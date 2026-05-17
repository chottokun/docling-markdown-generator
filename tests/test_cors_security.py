
from fastapi.testclient import TestClient
from mock_docling import mock_docling
mock_docling()

import docling_lib.config
import docling_lib.server
from docling_lib.server import create_app

def test_cors_restrictive_methods_and_headers(monkeypatch):
    # Set an allowed origin to trigger CORS logic
    origins = ["http://allowed.com"]
    monkeypatch.setattr(docling_lib.config, "CORS_ORIGINS", origins)
    monkeypatch.setattr(docling_lib.server, "CORS_ORIGINS", origins)

    app = create_app()
    client = TestClient(app)

    # Preflight request with an arbitrary method (e.g., DELETE)
    response = client.options(
        "/",
        headers={
            "Origin": "http://allowed.com",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "X-Custom-Header",
        },
    )

    # In the fixed version, this should be rejected
    assert response.status_code == 400

    # But GET/POST and Content-Type should be allowed
    response_ok = client.options(
        "/",
        headers={
            "Origin": "http://allowed.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response_ok.status_code == 200
    assert "POST" in response_ok.headers.get("access-control-allow-methods", "")
    assert "Content-Type" in response_ok.headers.get("access-control-allow-headers", "")

def test_cors_default_origin(monkeypatch):
    # By default, CORS_ORIGINS should be empty (more secure)
    monkeypatch.setattr(docling_lib.config, "CORS_ORIGINS", [])
    monkeypatch.setattr(docling_lib.server, "CORS_ORIGINS", [])

    app = create_app()
    client = TestClient(app)

    response = client.get("/", headers={"Origin": "http://example.com"})
    assert response.status_code == 200
    # No CORS header should be present when origins are not matched (empty list matches nothing)
    assert "access-control-allow-origin" not in response.headers

def test_cors_custom_origin(monkeypatch):
    # Set custom origins via patching the config and server
    origins = ["http://allowed.com", "http://another.com"]
    monkeypatch.setattr(docling_lib.config, "CORS_ORIGINS", origins)
    monkeypatch.setattr(docling_lib.server, "CORS_ORIGINS", origins)

    app = create_app()
    client = TestClient(app)

    # Allowed origin
    response = client.get("/", headers={"Origin": "http://allowed.com"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://allowed.com"

    # Disallowed origin
    response = client.get("/", headers={"Origin": "http://disallowed.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
