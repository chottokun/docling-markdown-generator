from fastapi.testclient import TestClient

import docling_lib.config
from docling_lib.server import create_app


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


def test_cors_preflight(monkeypatch):
    origins = ["http://allowed.com"]
    monkeypatch.setattr(docling_lib.config, "CORS_ORIGINS", origins)
    monkeypatch.setattr(docling_lib.server, "CORS_ORIGINS", origins)

    app = create_app()
    client = TestClient(app)

    # Preflight request
    response = client.options(
        "/",
        headers={
            "Origin": "http://allowed.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://allowed.com"
    assert "POST" in response.headers.get("access-control-allow-methods")
