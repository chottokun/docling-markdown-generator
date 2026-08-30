from unittest.mock import MagicMock

import pytest
from PIL import Image

from docling_lib.vlm import generate_caption, generate_caption_sync


def test_ollama_caption_sync_success_mock(monkeypatch):
    """Verifies synchronous Ollama caption generation with a mocked HTTP response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {"content": "Mocked Ollama image description."}
    }

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    monkeypatch.setattr("httpx.Client", lambda **kwargs: mock_client)

    img = Image.new("RGB", (20, 20), color="blue")
    result = generate_caption_sync(
        image=img,
        provider="ollama",
        model="qwen2-vl:2b",
        endpoint="http://localhost:11434",
    )

    assert result == "Mocked Ollama image description."
    mock_client.post.assert_called_once()
    url, kwargs = mock_client.post.call_args
    assert "api/chat" in url[0]
    assert kwargs["json"]["model"] == "qwen2-vl:2b"


@pytest.mark.asyncio
async def test_ollama_caption_async_success_mock(monkeypatch):
    """Verifies asynchronous Ollama caption generation with a mocked HTTP response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {"content": "Mocked async Ollama caption."}
    }

    mock_async_client = MagicMock()
    mock_async_client.__aenter__.return_value = mock_async_client

    async def mock_post(*args, **kwargs):
        return mock_response

    mock_async_client.post = mock_post

    monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: mock_async_client)

    img = Image.new("RGB", (20, 20), color="red")
    result = await generate_caption(
        image=img,
        provider="ollama",
        model="qwen2-vl:2b",
        endpoint="http://localhost:11434",
    )

    assert result == "Mocked async Ollama caption."
