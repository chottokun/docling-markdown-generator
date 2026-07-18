import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image

# Mock docling and torch before importing PDFConverter
from tests.mock_docling import mock_docling
mock_docling()

from docling_core.types.doc import (
    TableCell,
    TableData,
)
from docling_lib.converter import (
    DocumentConversionOptions,
    PDFConverter,
)
from docling_lib.vlm import (
    generate_caption,
    generate_caption_sync,
    get_semaphore,
)
from docling_lib.utils import serialize_table_data_to_markdown


class TestMultiProviderVLMAndRates(unittest.TestCase):

    @patch("httpx.Client")
    def test_openai_provider_payload(self, mock_client_cls):
        """
        Verify that OpenAI provider prepares and executes correct chat completions payload.
        """
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "OpenAI Description"}}]
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
        self.assertTrue(content_parts[1]["image_url"]["url"].startswith("data:image/png;base64,"))

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
            TableCell(start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=0, end_col_offset_idx=1, text="Header | Name"),
            TableCell(start_row_offset_idx=1, end_row_offset_idx=2, start_col_offset_idx=0, end_col_offset_idx=1, text="Alice | Bob"),
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
        from docling_lib.server import get_conversion_request

        # Run direct call of the Form parser dependency with custom parameters
        req = get_conversion_request(
            table_format="markdown",
            include_page_breaks=True,
            include_kv_extraction=True,
            vlm_enabled=True,
            vlm_provider="anthropic",
            vlm_api_key="api-key-xyz",
            vlm_model="claude-3-5-sonnet-20241022",
            vlm_endpoint="https://api.anthropic.com",
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
        self.assertEqual(req.vlm_endpoint, "https://api.anthropic.com")
        self.assertEqual(req.vlm_prompt, "Write caption in English")
        self.assertEqual(req.vlm_max_concurrent, 10)
        self.assertEqual(req.num_threads, 8)
        self.assertTrue(req.cuda_use_flash_attention)


if __name__ == "__main__":
    unittest.main()
