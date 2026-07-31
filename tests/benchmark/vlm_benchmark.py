import asyncio
import time
import unittest.mock as mock

import httpx

from docling_lib.vlm import generate_caption, generate_caption_sync


def mock_transport_benchmark():
    # Mocking post to return a 200 response
    mock_resp = mock.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"message": {"content": "Success"}}

    # We patch Client.post and AsyncClient.post
    async def mock_async_post(*args, **kwargs):
        return mock_resp

    with (
        mock.patch("httpx.Client.post", return_value=mock_resp),
        mock.patch("httpx.AsyncClient.post", side_effect=mock_async_post),
    ):
        # Benchmark sync
        start = time.perf_counter()
        for _ in range(50):
            generate_caption_sync(provider="ollama", endpoint="http://localhost:11434")
        sync_duration = time.perf_counter() - start
        print(f"Sync baseline duration (50 iterations): {sync_duration:.4f}s")

        # Benchmark async
        async def run_async():
            start = time.perf_counter()
            for _ in range(50):
                await generate_caption(
                    provider="ollama", endpoint="http://localhost:11434"
                )
            async_duration = time.perf_counter() - start
            print(f"Async baseline duration (50 iterations): {async_duration:.4f}s")

        asyncio.run(run_async())


if __name__ == "__main__":
    mock_transport_benchmark()
