from pathlib import Path

import httpx
import pytest

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
def reset_model_pool():
    """Reset model pool and default converter before each test to ensure isolation."""
    try:
        import docling_lib.converter
        docling_lib.converter._default_pdf_converter = None
        if hasattr(docling_lib.converter, "_model_pool"):
            docling_lib.converter._model_pool.clear()
    except ImportError:
        pass
