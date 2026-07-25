import os
from pathlib import Path

import httpx
import pytest

# Set default API key environment variable before imports to ensure configuration in tests
os.environ.setdefault("DOCLING_API_KEY", "test-api-key")

TEST_DATA_DIR = Path(__file__).parent / "test_data"


@pytest.fixture(scope="session")
def file_downloader():
    """
    A pytest fixture that provides a function to download test files.
    The downloaded files are cached in the 'test_data' directory to avoid
    re-downloading during the same test session.
    Uses httpx.Client for connection pooling and better performance.
    """
    try:
        import requests  # noqa: F401
    except ImportError:
        pytest.skip("requests not installed, skipping downloader fixture")

    TEST_DATA_DIR.mkdir(exist_ok=True)

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:

        def _downloader(url: str) -> Path:
            filename = url.split("/")[-1]
            file_path = TEST_DATA_DIR / filename

            if not file_path.exists():
                response = client.get(url)
                response.raise_for_status()
                file_path.write_bytes(response.content)

            return file_path

        yield _downloader


@pytest.fixture(scope="session")
def pdf_downloader(file_downloader):
    """Fixture specifically for PDF files."""
    return file_downloader


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter in-memory storage before each test."""
    try:
        import docling_lib.server
        docling_lib.server._rate_limit_data.clear()
    except ImportError:
        # Ignore if docling_lib.server cannot be imported (e.g. lightweight tests without docling)
        pass


@pytest.fixture(autouse=True)
def bypass_auth(request):
    """Bypass API key authentication for all tests except security auth tests."""
    try:
        from docling_lib.server import app, api_key_auth
        if "test_security_auth_rate_limit" in request.node.nodeid:
            app.dependency_overrides.pop(api_key_auth, None)
        else:
            app.dependency_overrides[api_key_auth] = lambda: None
    except ImportError:
        pass
