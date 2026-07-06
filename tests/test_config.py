import importlib
import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest

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


def test_setup_logging_idempotency():
    """Verify that calling setup_logging multiple times does not raise errors."""
    config.setup_logging()
    config.setup_logging()


def test_env_overrides():
    """Verify that environment variables correctly override default configurations."""
    custom_env = {
        "DOCLING_UPLOAD_DIR": "/tmp/custom_uploads",
        "DOCLING_OUTPUT_DIR": "/tmp/custom_output",
        "DOCLING_MAX_UPLOAD_SIZE": "1048576",
        "DOCLING_CORS_ORIGINS": " http://localhost:3000 , https://example.com ",
        "DOCLING_API_KEY": "secret-key",
        "DOCLING_RATE_LIMIT_REQUESTS": "10",
        "DOCLING_RATE_LIMIT_WINDOW": "120",
        "DOCLING_DO_FORMULA": "False",
        "DOCLING_DO_OCR": "false",
        "DOCLING_DO_CHART": "True",
        "DOCLING_DO_CODE": "true",
        "DOCLING_USE_GPU": "False",
    }

    with patch.dict(os.environ, custom_env):
        importlib.reload(config)
        assert config.UPLOAD_DIR == Path("/tmp/custom_uploads")
        assert config.OUTPUT_DIR == Path("/tmp/custom_output")
        assert config.MAX_UPLOAD_SIZE == 1048576
        assert config.CORS_ORIGINS == ["http://localhost:3000", "https://example.com"]
        assert config.API_KEY == "secret-key"
        assert config.RATE_LIMIT_REQUESTS == 10
        assert config.RATE_LIMIT_WINDOW == 120
        assert config.DO_FORMULA is False
        assert config.DO_OCR is False
        assert config.DO_CHART is True
        assert config.DO_CODE is True
        assert config.USE_GPU is False

    # Test empty CORS_ORIGINS
    with patch.dict(os.environ, {"DOCLING_CORS_ORIGINS": ""}):
        importlib.reload(config)
        assert config.CORS_ORIGINS == []

    # Clean up: reload config with original environment to avoid side effects on other tests
    importlib.reload(config)
