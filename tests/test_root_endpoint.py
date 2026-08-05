from fastapi.testclient import TestClient
import docling_lib.config
import docling_lib.server
from docling_lib.server import app, create_app

client = TestClient(app)

def test_root_get_success():
    """
    Assert that a GET request to the root endpoint (/) returns 200 OK
    and the correct JSON welcome message.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "").lower()
    assert response.json() == {
        "message": "Welcome to the Docling Markdown Conversion Server"
    }

def test_root_options_cors(monkeypatch):
    """
    Assert that an OPTIONS request to the root endpoint (/) returns 200 OK
    and the appropriate Access-Control-Allow-Origin header is present under CORS rules
    when the origin is allowed.
    """
    # Configure custom CORS origins
    allowed_origin = "http://localhost:3000"
    monkeypatch.setattr(docling_lib.config, "CORS_ORIGINS", [allowed_origin])
    monkeypatch.setattr(docling_lib.server, "CORS_ORIGINS", [allowed_origin])

    # Instantiate custom app with patched configuration
    local_app = create_app()
    local_client = TestClient(local_app)

    response = local_client.options(
        "/",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == allowed_origin
