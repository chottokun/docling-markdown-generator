import logging
from unittest.mock import patch
import pytest
from PIL import Image

# Mock docling and torch before importing vlm or PDFConverter
from tests.mock_docling import mock_docling

mock_docling()

from docling_lib.vlm import generate_caption, generate_caption_sync


def test_generate_caption_sync_encoding_exception(caplog):
    """
    Verify that an exception raised during image base64 encoding in
    generate_caption_sync is handled gracefully, logging a warning
    and returning an empty string.
    """
    img = Image.new("RGB", (100, 100))

    # Mock _encode_image_to_base64 to raise an exception
    with patch(
        "docling_lib.vlm._encode_image_to_base64",
        side_effect=ValueError("Simulated base64 encoding error"),
    ):
        with caplog.at_level(logging.WARNING):
            result = generate_caption_sync(image=img)

    # Assertions
    assert result == ""
    assert "Failed to encode image to base64 for VLM:" in caplog.text
    assert "Simulated base64 encoding error" in caplog.text


@pytest.mark.asyncio
async def test_generate_caption_encoding_exception(caplog):
    """
    Verify that an exception raised during image base64 encoding in
    generate_caption is handled gracefully, logging a warning
    and returning an empty string.
    """
    img = Image.new("RGB", (100, 100))

    # Mock _encode_image_to_base64 to raise an exception
    with patch(
        "docling_lib.vlm._encode_image_to_base64",
        side_effect=ValueError("Simulated base64 encoding error"),
    ):
        with caplog.at_level(logging.WARNING):
            result = await generate_caption(image=img)

    # Assertions
    assert result == ""
    assert "Failed to encode image to base64 for VLM:" in caplog.text
    assert "Simulated base64 encoding error" in caplog.text
