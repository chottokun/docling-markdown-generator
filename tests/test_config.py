import logging
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
