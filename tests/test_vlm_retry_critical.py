import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from PIL import Image

from docling_lib.vlm import generate_caption, generate_caption_sync


class TestCriticalVLMRetries(unittest.TestCase):
    """批判的な視点でのVLMリトライ・フォールバック機能の検証テスト"""

    def setUp(self):
        self.img = Image.new("RGB", (10, 10))

    # --- 同期版 (generate_caption_sync) の批判的検証 ---

    @patch("httpx.Client")
    def test_sync_retry_on_503_and_eventual_success(self, mock_client_cls):
        """503エラー発生時にリトライし、2回目で成功するケース"""
        mock_client = mock_client_cls.return_value.__enter__.return_value

        res_503 = MagicMock()
        res_503.status_code = 503
        err_503 = httpx.HTTPStatusError("503 Service Unavailable", request=MagicMock(), response=res_503)

        res_200 = MagicMock()
        res_200.json.return_value = {"message": {"content": "503 recovered"}}
        res_200.raise_for_status = MagicMock()

        mock_client.post.side_effect = [err_503, res_200]

        res = generate_caption_sync(
            image=self.img,
            provider="ollama",
            max_retries=2,
            base_delay=0.001,
        )
        self.assertEqual(res, "503 recovered")
        self.assertEqual(mock_client.post.call_count, 2)

    @patch("httpx.Client")
    def test_sync_non_retryable_400_fails_fast(self, mock_client_cls):
        """400 Bad Request（非一時的エラー）の場合はリトライせず即座に空文字を返すこと"""
        mock_client = mock_client_cls.return_value.__enter__.return_value

        res_400 = MagicMock()
        res_400.status_code = 400
        err_400 = httpx.HTTPStatusError("400 Bad Request", request=MagicMock(), response=res_400)
        mock_client.post.side_effect = err_400

        res = generate_caption_sync(
            image=self.img,
            provider="ollama",
            max_retries=3,
            base_delay=0.001,
        )
        self.assertEqual(res, "")
        # リトライされず1回の呼び出しで終了すること
        self.assertEqual(mock_client.post.call_count, 1)

    @patch("httpx.Client")
    def test_sync_exhausted_retries_returns_empty_string(self, mock_client_cls):
        """最大リトライ回数を超過した場合は例外を外に漏らさず空文字を返すこと"""
        mock_client = mock_client_cls.return_value.__enter__.return_value

        res_429 = MagicMock()
        res_429.status_code = 429
        err_429 = httpx.HTTPStatusError("429 Too Many Requests", request=MagicMock(), response=res_429)
        mock_client.post.side_effect = err_429

        res = generate_caption_sync(
            image=self.img,
            provider="ollama",
            max_retries=2,
            base_delay=0.001,
        )
        self.assertEqual(res, "")
        # 初回 + リトライ2回 = 計3回
        self.assertEqual(mock_client.post.call_count, 3)

    # --- 非同期版 (generate_caption) の批判的検証 ---

    def test_async_retry_on_429_success(self):
        """非同期版: 429エラー時にリトライして2回目で成功するケース"""
        async def run_test():
            with patch("docling_lib.vlm._get_cached_async_client") as mock_get_client:
                mock_client = AsyncMock()
                mock_get_client.return_value = mock_client

                res_429 = MagicMock()
                res_429.status_code = 429
                err_429 = httpx.HTTPStatusError("429 Rate Limit", request=MagicMock(), response=res_429)

                res_200 = MagicMock()
                res_200.json.return_value = {"choices": [{"message": {"content": "Async 429 recovered"}}]}
                res_200.raise_for_status = MagicMock()

                mock_client.post.side_effect = [err_429, res_200]

                res = await generate_caption(
                    image=self.img,
                    provider="openai",
                    api_key="test-key",
                    max_retries=2,
                    base_delay=0.001,
                )
                self.assertEqual(res, "Async 429 recovered")
                self.assertEqual(mock_client.post.call_count, 2)

        asyncio.run(run_test())

    def test_async_non_retryable_404_fails_fast(self):
        """非同期版: 404エラーの場合はリトライせず即座に終了すること"""
        async def run_test():
            with patch("docling_lib.vlm._get_cached_async_client") as mock_get_client:
                mock_client = AsyncMock()
                mock_get_client.return_value = mock_client

                res_404 = MagicMock()
                res_404.status_code = 404
                err_404 = httpx.HTTPStatusError("404 Not Found", request=MagicMock(), response=res_404)
                mock_client.post.side_effect = err_404

                res = await generate_caption(
                    image=self.img,
                    provider="ollama",
                    max_retries=3,
                    base_delay=0.001,
                )
                self.assertEqual(res, "")
                self.assertEqual(mock_client.post.call_count, 1)

        asyncio.run(run_test())

    def test_async_network_error_retries_and_recovers(self):
        """非同期版: ネットワーク切断(RequestError)時にリトライして復帰すること"""
        async def run_test():
            with patch("docling_lib.vlm._get_cached_async_client") as mock_get_client:
                mock_client = AsyncMock()
                mock_get_client.return_value = mock_client

                err_net = httpx.ConnectError("Connection refused")

                res_200 = MagicMock()
                res_200.json.return_value = {"message": {"content": "Network recovered"}}
                res_200.raise_for_status = MagicMock()

                mock_client.post.side_effect = [err_net, res_200]

                res = await generate_caption(
                    image=self.img,
                    provider="ollama",
                    max_retries=1,
                    base_delay=0.001,
                )
                self.assertEqual(res, "Network recovered")
                self.assertEqual(mock_client.post.call_count, 2)

        asyncio.run(run_test())
