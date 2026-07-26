import os
import sys
import time
from unittest.mock import MagicMock, patch
import pytest
from fastapi import Request
from pathlib import Path
from docling_core.types.doc import DoclingDocument

import docling_lib.converter as converter
from docling_lib.converter import is_cuda_compatible, PDFConverter, DocumentConversionOptions
import docling_lib.server as server
from docling_lib.server import rate_limiter, _rate_limit_data


def test_is_cuda_compatible_caching(monkeypatch):
    """
    Verify that is_cuda_compatible implements caching and stores the result
    in the global private cache variable when not running under pytest.
    """
    # Reset cache
    converter._cuda_compatible_cache = None

    # We use monkeypatch to temporarily delete PYTEST_CURRENT_TEST to simulate production
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    # We mock torch.cuda.is_available to count calls
    with patch("docling_lib.converter.torch.cuda.is_available") as mock_is_available:
        mock_is_available.return_value = False

        # First call should run the computation
        res1 = is_cuda_compatible()
        assert res1 is False
        assert mock_is_available.call_count == 1
        assert converter._cuda_compatible_cache is False

        # Second call should hit the cache and not call is_available again
        res2 = is_cuda_compatible()
        assert res2 is False
        assert mock_is_available.call_count == 1


def test_save_images_single_image_bypass(tmp_path):
    """
    Verify that _save_images bypasses ThreadPoolExecutor when there is only one image.
    """
    converter_inst = PDFConverter(options=DocumentConversionOptions())
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    # Create mock document with exactly 1 picture
    mock_doc = MagicMock(spec=DoclingDocument)
    mock_picture = MagicMock()
    mock_doc.pictures = [mock_picture]

    # We patch ThreadPoolExecutor to verify it is NEVER instantiated
    with patch("docling_lib.converter.ThreadPoolExecutor") as MockExecutor:
        converter_inst._save_images(mock_doc, images_dir)
        MockExecutor.assert_not_called()
        # Verify the single image save was called directly on calling thread
        mock_picture.image.pil_image.save.assert_called_once()


def test_save_images_multiple_images_executor(tmp_path):
    """
    Verify that _save_images uses ThreadPoolExecutor with dynamic workers when there are multiple images.
    """
    converter_inst = PDFConverter(options=DocumentConversionOptions())
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    mock_doc = MagicMock(spec=DoclingDocument)
    mock_picture1 = MagicMock()
    mock_picture2 = MagicMock()
    mock_doc.pictures = [mock_picture1, mock_picture2]

    with patch("docling_lib.converter.ThreadPoolExecutor", return_value=MagicMock()) as MockExecutor:
        converter_inst._save_images(mock_doc, images_dir)
        # Should call ThreadPoolExecutor with max_workers=2
        MockExecutor.assert_called_once_with(max_workers=2)


@pytest.mark.asyncio
async def test_rate_limiter_memory_cleanup():
    """
    Verify that rate_limiter periodic cleanup successfully deletes inactive client IP records,
    fully resolving any memory leak/growth concerns.
    """
    # Clear rate limiter data
    _rate_limit_data.clear()
    server._last_rate_limit_cleanup = 0.0

    # Create two requests from different IPs
    req1 = MagicMock(spec=Request)
    req1.client.host = "1.1.1.1"
    req1.headers = {}

    req2 = MagicMock(spec=Request)
    req2.client.host = "2.2.2.2"
    req2.headers = {}

    start_time = 1000.0

    # 1. First requests at start_time
    with patch("time.time", return_value=start_time):
        await rate_limiter(req1)
        await rate_limiter(req2)

    assert "1.1.1.1" in _rate_limit_data
    assert "2.2.2.2" in _rate_limit_data
    assert len(_rate_limit_data) == 2

    # 2. Advance time past window and past cleanup interval
    # RATE_LIMIT_WINDOW is 60, cleanup interval is 600
    future_time = start_time + 650.0

    with patch("time.time", return_value=future_time):
        # Trigger rate limiter with a third client
        req3 = MagicMock(spec=Request)
        req3.client.host = "3.3.3.3"
        req3.headers = {}

        await rate_limiter(req3)

    # After periodic cleanup, inactive and expired IPs (1.1.1.1 and 2.2.2.2)
    # must be completely removed from the dictionary!
    assert "1.1.1.1" not in _rate_limit_data
    assert "2.2.2.2" not in _rate_limit_data
    assert "3.3.3.3" in _rate_limit_data
    assert len(_rate_limit_data) == 1
