from fastapi.testclient import TestClient
from docling_lib.server import app
import os
import importlib
import docling_lib.config
import docling_lib.server

def test_cors_default_origin():
    # By default, CORS_ORIGINS is ["*"]
    client = TestClient(app)
    response = client.get("/", headers={"Origin": "http://example.com"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"

def test_cors_custom_origin(monkeypatch):
    # Set custom origins
    monkeypatch.setenv("DOCLING_CORS_ORIGINS", "http://allowed.com,http://another.com")

    # Reload config and server to apply new env var
    importlib.reload(docling_lib.config)
    importlib.reload(docling_lib.server)

    client = TestClient(docling_lib.server.app)

    # Allowed origin
    response = client.get("/", headers={"Origin": "http://allowed.com"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://allowed.com"

    # Disallowed origin
    response = client.get("/", headers={"Origin": "http://disallowed.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers

def test_cors_preflight(monkeypatch):
    monkeypatch.setenv("DOCLING_CORS_ORIGINS", "http://allowed.com")
    importlib.reload(docling_lib.config)
    importlib.reload(docling_lib.server)

    client = TestClient(docling_lib.server.app)

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
