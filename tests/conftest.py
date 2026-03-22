from pathlib import Path

import pytest
import requests

TEST_DATA_DIR = Path(__file__).parent / "test_data"


@pytest.fixture(scope="session")
def file_downloader():
    """
    A pytest fixture that provides a function to download test files.
    The downloaded files are cached in the 'test_data' directory to avoid
    re-downloading during the same test session.
    """
    TEST_DATA_DIR.mkdir(exist_ok=True)

    def _downloader(url: str) -> Path:
        filename = url.split("/")[-1]
        file_path = TEST_DATA_DIR / filename

        if not file_path.exists():
            response = requests.get(url)
            response.raise_for_status()
            with open(file_path, "wb") as f:
                f.write(response.content)

        return file_path

    return _downloader


@pytest.fixture(scope="session")
def pdf_downloader(file_downloader):
    """Fixture specifically for PDF files."""
    return file_downloader
