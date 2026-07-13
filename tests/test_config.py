import importlib
import logging
import os
from pathlib import Path
from unittest.mock import patch

from docling_lib import config


def test_constants():
    """Verify that constants have the expected values."""
    assert config.MD_OUTPUT_NAME == "processed_document.md"
    assert config.IMAGE_DIR_NAME == "images"
    assert config.IMAGE_RESOLUTION_SCALE == 2.0


@patch("logging.basicConfig")
def test_setup_logging(mock_basicConfig):
    """Verify that setup_logging calls basicConfig with correct parameters."""
    config.setup_logging()
    mock_basicConfig.assert_called_once_with(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )


def test_setup_logging_idempotent():
    """Verify that setup_logging can be called multiple times safely."""
    # It just calls basicConfig, which is safe to call multiple times in standard logging
    config.setup_logging()
    config.setup_logging()


def test_environment_variable_overrides():
    """Verify that configuration constants are correctly updated from environment variables."""
    env_vars = {
        "DOCLING_UPLOAD_DIR": "/tmp/uploads",
        "DOCLING_OUTPUT_DIR": "/tmp/output",
        "DOCLING_MAX_UPLOAD_SIZE": "1048576",
        "DOCLING_CORS_ORIGINS": "http://localhost:3000, https://example.com",
        "DOCLING_API_KEY": "test_api_key",
        "DOCLING_RATE_LIMIT_REQUESTS": "10",
        "DOCLING_RATE_LIMIT_WINDOW": "120",
        "DOCLING_DO_FORMULA": "False",
        "DOCLING_DO_OCR": "false",
        "DOCLING_DO_CHART": "True",
        "DOCLING_DO_CODE": "true",
        "DOCLING_USE_GPU": "FALSE",
    }

    with patch.dict(os.environ, env_vars):
        importlib.reload(config)
        try:
            assert config.UPLOAD_DIR == Path("/tmp/uploads")
            assert config.OUTPUT_DIR == Path("/tmp/output")
            assert config.MAX_UPLOAD_SIZE == 1048576
            assert config.CORS_ORIGINS == {"http://localhost:3000", "https://example.com"}
            assert config.API_KEY == "test_api_key"
            assert config.RATE_LIMIT_REQUESTS == 10
            assert config.RATE_LIMIT_WINDOW == 120
            assert config.DO_FORMULA is False
            assert config.DO_OCR is False
            assert config.DO_CHART is True
            assert config.DO_CODE is True
            assert config.USE_GPU is False
        finally:
            # Restore defaults for other tests by reloading again without the env vars
            importlib.reload(config)


def test_environment_variable_defaults():
    """Verify default values when environment variables are not set."""
    with patch.dict(os.environ, {}, clear=True):
        importlib.reload(config)
        try:
            assert config.UPLOAD_DIR == Path("uploads")
            assert config.OUTPUT_DIR == Path("output")
            assert config.MAX_UPLOAD_SIZE == 20 * 1024 * 1024
            assert config.CORS_ORIGINS == set()
            assert config.API_KEY is None
            assert config.RATE_LIMIT_REQUESTS == 5
            assert config.RATE_LIMIT_WINDOW == 60
            assert config.DO_FORMULA is True
            assert config.DO_OCR is True
            assert config.DO_CHART is False
            assert config.DO_CODE is False
            assert config.USE_GPU is True
        finally:
            importlib.reload(config)
