from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from docling_lib.vlm import generate_caption, generate_caption_sync


def test_generate_caption_sync_encoding_exception():
    """
    Verify that an exception raised during image encoding in generate_caption_sync
    is handled gracefully, logs a warning, and returns an empty string.
    """
    mock_image = MagicMock(spec=Image.Image)
    mock_image.save.side_effect = OSError("Encoding failed")

    with patch("docling_lib.vlm.logger") as mock_logger:
        result = generate_caption_sync(image=mock_image)
        assert result == ""
        mock_logger.warning.assert_called_once()
        # Also ensure that warning contains the message
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "Failed to encode image to base64 for VLM" in warning_msg

@pytest.mark.asyncio
async def test_generate_caption_encoding_exception():
    """
    Verify that an exception raised during image encoding in generate_caption
    is handled gracefully, logs a warning, and returns an empty string.
    """
    mock_image = MagicMock(spec=Image.Image)
    mock_image.save.side_effect = OSError("Encoding failed")

    with patch("docling_lib.vlm.logger") as mock_logger:
        result = await generate_caption(image=mock_image)
        assert result == ""
        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "Failed to encode image to base64 for VLM" in warning_msg
