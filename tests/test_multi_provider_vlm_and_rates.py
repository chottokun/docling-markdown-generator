import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

# Mock docling and torch before importing PDFConverter
from tests.mock_docling import mock_docling

mock_docling()

from docling_core.types.doc import (
    TableCell,
    TableData,
)

from docling_lib.utils import serialize_table_data_to_markdown
from docling_lib.vlm import (
    generate_caption_sync,
    get_semaphore,
)


class TestMultiProviderVLMAndRates(unittest.TestCase):
    @patch("httpx.Client")
    def test_openai_provider_payload(self, mock_client_cls):
        """
        Verify that OpenAI provider prepares and executes correct chat completions payload.
        """
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"role": "assistant", "content": "OpenAI Description"}}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        img = Image.new("RGB", (10, 10))
        res = generate_caption_sync(
            image=img,
            provider="openai",
            api_key="sk-test-key",
            model="gpt-4o-mini",
            endpoint="https://api.openai.com/v1",
            prompt="Describe this",
        )

        self.assertEqual(res, "OpenAI Description")
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args[1]
        self.assertEqual(call_kwargs["headers"]["Authorization"], "Bearer sk-test-key")
        self.assertEqual(call_kwargs["json"]["model"], "gpt-4o-mini")
        content_parts = call_kwargs["json"]["messages"][0]["content"]
        self.assertEqual(content_parts[0]["text"], "Describe this")
        self.assertTrue(
            content_parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
        )

    @patch("httpx.Client")
    def test_anthropic_provider_payload(self, mock_client_cls):
        """
        Verify that Anthropic provider prepares and executes correct messages payload.
        """
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"text": "Anthropic Description"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        img = Image.new("RGB", (10, 10))
        res = generate_caption_sync(
            image=img,
            provider="anthropic",
            api_key="cl-test-key",
            model="claude-3-5-sonnet-20241022",
            endpoint="https://api.anthropic.com",
            prompt="Describe",
        )

        self.assertEqual(res, "Anthropic Description")
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args[1]
        self.assertEqual(call_kwargs["headers"]["x-api-key"], "cl-test-key")
        self.assertEqual(call_kwargs["headers"]["anthropic-version"], "2023-06-01")
        messages = call_kwargs["json"]["messages"][0]["content"]
        self.assertEqual(messages[0]["type"], "image")
        self.assertEqual(messages[1]["text"], "Describe")

    @patch("httpx.Client")
    def test_google_provider_payload(self, mock_client_cls):
        """
        Verify that Google Gemini provider prepares and executes correct content payload.
        """
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Gemini Description"}]}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        img = Image.new("RGB", (10, 10))
        res = generate_caption_sync(
            image=img,
            provider="google",
            api_key="gem-test-key",
            model="gemini-1.5-flash",
            endpoint="https://generativelanguage.googleapis.com",
            prompt="Explain",
        )

        self.assertEqual(res, "Gemini Description")
        mock_client.post.assert_called_once()
        url_called = mock_client.post.call_args[0][0]
        self.assertIn("key=gem-test-key", url_called)
        self.assertIn("gemini-1.5-flash", url_called)

    def test_generate_caption_sync_semaphore_acquire_exception(self):
        """
        Verify that generate_caption_sync handles semaphore acquire exception gracefully,
        returns empty string, and does not release the semaphore since it was never acquired.
        """
        from docling_lib.vlm import get_semaphore
        real_sem = get_semaphore(5, provider="ollama", endpoint="http://localhost:11434")

        mock_sem = MagicMock(wraps=real_sem)
        # Mock acquire method to raise Exception
        mock_sem.acquire.side_effect = Exception("Semaphore acquisition failed")

        with patch("docling_lib.vlm.get_semaphore", return_value=mock_sem):
            img = Image.new("RGB", (10, 10))
            res = generate_caption_sync(
                image=img,
                provider="ollama",
                endpoint="http://localhost:11434",
            )
            self.assertEqual(res, "")
            mock_sem.acquire.assert_called_once()
            mock_sem.release.assert_not_called()

    @patch("httpx.Client")
    def test_generate_caption_sync_client_context_exception(self, mock_client_cls):
        """
        Verify that generate_caption_sync handles exception raised inside the context manager gracefully,
        logs warning, returns empty string, and properly releases the semaphore.
        """
        # Mock __enter__ of Client context manager to throw Exception
        mock_client = mock_client_cls.return_value
        mock_client.__enter__.side_effect = Exception("Context manager enter failed")

        from docling_lib.vlm import get_semaphore
        real_sem = get_semaphore(5, provider="ollama", endpoint="http://localhost:11434")

        mock_sem = MagicMock(wraps=real_sem)
        with patch("docling_lib.vlm.get_semaphore", return_value=mock_sem):
            img = Image.new("RGB", (10, 10))
            res = generate_caption_sync(
                image=img,
                provider="ollama",
                endpoint="http://localhost:11434",
            )
            self.assertEqual(res, "")
            mock_sem.acquire.assert_called_once()
            mock_sem.release.assert_called_once()

    @patch("httpx.Client")
    def test_generate_caption_sync_post_exception(self, mock_client_cls):
        """
        Verify that generate_caption_sync handles post exception gracefully,
        logs warning, returns empty string, and properly releases the semaphore.
        """
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.side_effect = Exception("HTTP post failure")

        # Mock get_semaphore to return a spy/mock semaphore
        from docling_lib.vlm import get_semaphore
        real_sem = get_semaphore(5, provider="ollama", endpoint="http://localhost:11434")

        mock_sem = MagicMock(wraps=real_sem)
        with patch("docling_lib.vlm.get_semaphore", return_value=mock_sem):
            img = Image.new("RGB", (10, 10))
            res = generate_caption_sync(
                image=img,
                provider="ollama",
                endpoint="http://localhost:11434",
            )
            self.assertEqual(res, "")
            mock_sem.acquire.assert_called_once()
            mock_sem.release.assert_called_once()

    def test_semaphore_rate_limiting_isolation(self):
        """
        Verify that rate-limiting semaphores are isolated per provider & endpoint.
        """
        sem1 = get_semaphore(3, provider="ollama", endpoint="http://localhost:11434")
        sem2 = get_semaphore(3, provider="ollama", endpoint="http://localhost:11434")
        self.assertIs(sem1, sem2)  # Same params -> Same semaphore

        # Different provider -> Different semaphore
        sem3 = get_semaphore(3, provider="openai", endpoint="https://api.openai.com/v1")
        self.assertIsNot(sem1, sem3)

        # Test acquiring limit
        self.assertTrue(sem1.acquire(blocking=False))
        self.assertTrue(sem1.acquire(blocking=False))
        self.assertTrue(sem1.acquire(blocking=False))
        self.assertFalse(sem1.acquire(blocking=False))  # Exceeded limit of 3

        # sem3 should be completely untouched and isolated
        self.assertTrue(sem3.acquire(blocking=False))

        # Cleanup
        sem1.release()
        sem1.release()
        sem1.release()
        sem3.release()

    @patch("httpx.Client")
    def test_default_endpoints_adjustment(self, mock_client_cls):
        """
        Verify default endpoints are automatically adjusted based on selected provider.
        """
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"text": "OK"}]}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        img = Image.new("RGB", (5, 5))
        # Call with default Ollama endpoint but selected "anthropic" provider
        generate_caption_sync(
            image=img,
            provider="anthropic",
            endpoint="http://localhost:11434",  # left as default
        )
        url_called = mock_client.post.call_args[0][0]
        # Should be automatically adjusted to Anthropic URL
        self.assertTrue(url_called.startswith("https://api.anthropic.com"))

    def test_escape_pipe_characters_in_markdown_table(self):
        """
        Verify serialize_table_data_to_markdown escapes pipe characters in table cell text.
        """
        cells = [
            TableCell(
                start_row_offset_idx=0,
                end_row_offset_idx=1,
                start_col_offset_idx=0,
                end_col_offset_idx=1,
                text="Header | Name",
            ),
            TableCell(
                start_row_offset_idx=1,
                end_row_offset_idx=2,
                start_col_offset_idx=0,
                end_col_offset_idx=1,
                text="Alice | Bob",
            ),
        ]
        td = TableData(table_cells=cells, num_rows=2, num_cols=1)
        md = serialize_table_data_to_markdown(td)

        self.assertIn("Header \\| Name", md)
        self.assertIn("Alice \\| Bob", md)
        self.assertNotIn("Header | Name", md)

    def test_fastapi_endpoint_params_mapping(self):
        """
        Verify server's Form dependency get_conversion_request correctly instantiates
        all of the new parameters and maps them to DocumentConversionRequest model.
        """
        from docling_lib.server import DOCLING_VLM_ENDPOINT, get_conversion_request

        # Run direct call of the Form parser dependency with custom parameters
        req = get_conversion_request(
            table_format="markdown",
            include_page_breaks=True,
            include_kv_extraction=True,
            vlm_enabled=True,
            vlm_provider="anthropic",
            vlm_api_key="api-key-xyz",
            vlm_model="claude-3-5-sonnet-20241022",
            vlm_prompt="Write caption in English",
            vlm_max_concurrent=10,
            num_threads=8,
            cuda_use_flash_attention=True,
        )

        self.assertEqual(req.table_format, "markdown")
        self.assertTrue(req.include_page_breaks)
        self.assertTrue(req.include_kv_extraction)
        self.assertTrue(req.vlm_enabled)
        self.assertEqual(req.vlm_provider, "anthropic")
        self.assertEqual(req.vlm_api_key, "api-key-xyz")
        self.assertEqual(req.vlm_model, "claude-3-5-sonnet-20241022")
        self.assertEqual(req.vlm_endpoint, DOCLING_VLM_ENDPOINT)
        self.assertEqual(req.vlm_prompt, "Write caption in English")
        self.assertEqual(req.vlm_max_concurrent, 10)
        self.assertEqual(req.num_threads, 8)
        self.assertTrue(req.cuda_use_flash_attention)


    def test_prepare_caption_args_directly(self):
        """
        Verify that _prepare_caption_args correctly resolves endpoints, defaults, and returns payload specs.
        """
        from docling_lib.vlm import _prepare_caption_args

        img = Image.new("RGB", (10, 10))
        res = _prepare_caption_args(
            image=img,
            provider="openai",
            api_key="sk-test",
            model="gpt-4o",
            endpoint="http://localhost:11434",  # left default
            prompt="Test prompt",
            text_content=None,
        )
        self.assertIsNotNone(res)
        provider_res, endpoint_res, url, headers, json_body = res
        self.assertEqual(provider_res, "openai")
        self.assertEqual(endpoint_res, "https://api.openai.com/v1")
        self.assertTrue(url.endswith("/chat/completions"))
        self.assertEqual(headers["Authorization"], "Bearer sk-test")
        self.assertEqual(json_body["model"], "gpt-4o")

        # Test invalid image returns None
        bad_img = MagicMock()
        bad_img.save.side_effect = Exception("Encoding failure")
        res_bad = _prepare_caption_args(
            image=bad_img,
            provider="ollama",
            api_key="",
            model="qwen2-vl:2b",
            endpoint="http://localhost:11434",
            prompt="Test",
            text_content=None,
        )
        self.assertIsNone(res_bad)


if __name__ == "__main__":
    unittest.main()

