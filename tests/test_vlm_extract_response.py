import unittest
from unittest.mock import patch

from tests.mock_docling import mock_docling

# Mock docling and torch before importing PDFConverter or anything else
mock_docling()

from docling_lib.vlm import _extract_response_content


class TestVLMExtractResponse(unittest.TestCase):
    def test_extract_response_openai_happy_path(self):
        """Test happy path for OpenAI, vLLM, and llama.cpp providers."""
        data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "This is a caption from OpenAI."
                    }
                }
            ]
        }
        for provider in ("openai", "vllm", "llama.cpp", "  OPENAI  ", "Vllm"):
            res = _extract_response_content(provider, data)
            self.assertEqual(res, "This is a caption from OpenAI.")

    def test_extract_response_anthropic_happy_path(self):
        """Test happy path for Anthropic provider."""
        data = {
            "content": [
                {
                    "type": "text",
                    "text": "This is a caption from Anthropic Claude."
                }
            ]
        }
        for provider in ("anthropic", "  ANTHROPIC  ", "Anthropic"):
            res = _extract_response_content(provider, data)
            self.assertEqual(res, "This is a caption from Anthropic Claude.")

    def test_extract_response_google_gemini_happy_path(self):
        """Test happy path for Google and Gemini providers."""
        data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "This is a caption from Google Gemini."
                            }
                        ]
                    }
                }
            ]
        }
        for provider in ("google", "gemini", "  GOOGLE  ", "Gemini"):
            res = _extract_response_content(provider, data)
            self.assertEqual(res, "This is a caption from Google Gemini.")

    def test_extract_response_ollama_happy_path(self):
        """Test happy path for Ollama provider."""
        data = {
            "message": {
                "role": "assistant",
                "content": "This is a caption from Ollama."
            }
        }
        for provider in ("ollama", "  Ollama  ", "OLLAMA"):
            res = _extract_response_content(provider, data)
            self.assertEqual(res, "This is a caption from Ollama.")

    def test_extract_response_ollama_fallback(self):
        """Test Ollama/default provider fallback when message content is missing."""
        data = {}
        res = _extract_response_content("ollama", data)
        self.assertEqual(res, "")

    @patch("docling_lib.vlm.logger")
    def test_extract_response_openai_errors(self, mock_logger):
        """Test error handling (KeyError, IndexError, TypeError) for OpenAI-compatible providers."""
        # KeyError: Missing 'choices'
        data_missing_choices = {}
        self.assertEqual(_extract_response_content("openai", data_missing_choices), "")
        mock_logger.warning.assert_called()
        mock_logger.warning.reset_mock()

        # IndexError: Empty 'choices' list
        data_empty_choices = {"choices": []}
        self.assertEqual(_extract_response_content("openai", data_empty_choices), "")
        mock_logger.warning.assert_called()
        mock_logger.warning.reset_mock()

        # KeyError: Missing 'message' key inside first choice
        data_missing_message = {"choices": [{}]}
        self.assertEqual(_extract_response_content("openai", data_missing_message), "")
        mock_logger.warning.assert_called()
        mock_logger.warning.reset_mock()

        # TypeError: 'choices' is a string instead of a list/dict
        data_type_error = {"choices": "not_a_list"}
        self.assertEqual(_extract_response_content("openai", data_type_error), "")
        mock_logger.warning.assert_called()

    @patch("docling_lib.vlm.logger")
    def test_extract_response_anthropic_errors(self, mock_logger):
        """Test error handling for Anthropic provider."""
        # KeyError: Missing 'content'
        data_missing_content = {}
        self.assertEqual(_extract_response_content("anthropic", data_missing_content), "")
        mock_logger.warning.assert_called()
        mock_logger.warning.reset_mock()

        # IndexError: Empty 'content' list
        data_empty_content = {"content": []}
        self.assertEqual(_extract_response_content("anthropic", data_empty_content), "")
        mock_logger.warning.assert_called()
        mock_logger.warning.reset_mock()

        # KeyError: Missing 'text' key inside first content block
        data_missing_text = {"content": [{}]}
        self.assertEqual(_extract_response_content("anthropic", data_missing_text), "")
        mock_logger.warning.assert_called()
        mock_logger.warning.reset_mock()

        # TypeError: 'content' is None
        data_type_error = {"content": None}
        self.assertEqual(_extract_response_content("anthropic", data_type_error), "")
        mock_logger.warning.assert_called()

    @patch("docling_lib.vlm.logger")
    def test_extract_response_google_gemini_errors(self, mock_logger):
        """Test error handling for Google Gemini provider."""
        # KeyError: Missing 'candidates'
        data_missing_candidates = {}
        self.assertEqual(_extract_response_content("google", data_missing_candidates), "")
        mock_logger.warning.assert_called()
        mock_logger.warning.reset_mock()

        # IndexError: Empty 'candidates' list
        data_empty_candidates = {"candidates": []}
        self.assertEqual(_extract_response_content("google", data_empty_candidates), "")
        mock_logger.warning.assert_called()
        mock_logger.warning.reset_mock()

        # KeyError: Missing 'content' inside candidate
        data_missing_content = {"candidates": [{}]}
        self.assertEqual(_extract_response_content("google", data_missing_content), "")
        mock_logger.warning.assert_called()
        mock_logger.warning.reset_mock()

        # KeyError: Missing 'parts' inside candidate content
        data_missing_parts = {"candidates": [{"content": {}}]}
        self.assertEqual(_extract_response_content("google", data_missing_parts), "")
        mock_logger.warning.assert_called()
        mock_logger.warning.reset_mock()

        # TypeError: 'candidates' is an integer
        data_type_error = {"candidates": 42}
        self.assertEqual(_extract_response_content("google", data_type_error), "")
        mock_logger.warning.assert_called()


if __name__ == "__main__":
    unittest.main()
