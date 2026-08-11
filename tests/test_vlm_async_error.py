import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from PIL import Image
import pytest
import httpx

from tests.mock_docling import mock_docling

mock_docling()

from docling_lib.vlm import generate_caption

@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_generate_caption_async_success(mock_async_client_cls):
    """
    Verify that generate_caption successfully calls httpx.AsyncClient and parses response.
    """
    mock_client = AsyncMock()
    mock_async_client_cls.return_value.__aenter__.return_value = mock_client

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"role": "assistant", "content": "This is an async caption."}
    }
    mock_response.raise_for_status = MagicMock()
    mock_client.post.return_value = mock_response

    img = Image.new("RGB", (10, 10))
    res = await generate_caption(
        image=img,
        provider="ollama",
        model="qwen2-vl:2b",
        endpoint="http://localhost:11434",
    )

    assert res == "This is an async caption."
    mock_client.post.assert_called_once()


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_generate_caption_async_post_exception(mock_async_client_cls):
    """
    Verify that generate_caption catches exceptions raised during post and returns "".
    """
    mock_client = AsyncMock()
    mock_async_client_cls.return_value.__aenter__.return_value = mock_client

    mock_client.post.side_effect = Exception("Async Connection Refused")

    img = Image.new("RGB", (10, 10))
    res = await generate_caption(
        image=img,
        provider="ollama",
        model="qwen2-vl:2b",
        endpoint="http://localhost:11434",
    )

    assert res == ""
    mock_client.post.assert_called_once()


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_generate_caption_async_http_status_error(mock_async_client_cls):
    """
    Verify that generate_caption catches HTTPStatusError and returns "".
    """
    mock_client = AsyncMock()
    mock_async_client_cls.return_value.__aenter__.return_value = mock_client

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        message="500 Internal Server Error",
        request=MagicMock(spec=httpx.Request),
        response=MagicMock(spec=httpx.Response),
    )
    mock_client.post.return_value = mock_response

    img = Image.new("RGB", (10, 10))
    res = await generate_caption(
        image=img,
        provider="openai",
        model="gpt-4o",
        endpoint="https://api.openai.com/v1",
    )

    assert res == ""
    mock_client.post.assert_called_once()
