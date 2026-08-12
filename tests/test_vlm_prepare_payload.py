import unittest

from docling_lib.vlm import _prepare_rest_payload


class TestVLMPreparePayload(unittest.TestCase):
    def test_openai_payload_no_image_no_api_key(self):
        url, headers, json_body = _prepare_rest_payload(
            provider="openai",
            model="gpt-4o",
            prompt="Hello World",
            img_base64=None,
            text_content=None,
            api_key="",
            endpoint="https://api.openai.com/v1",
        )
        self.assertEqual(url, "https://api.openai.com/v1/chat/completions")
        self.assertEqual(headers, {"Content-Type": "application/json"})
        self.assertEqual(json_body["model"], "gpt-4o")
        self.assertEqual(json_body["stream"], False)
        self.assertEqual(json_body["messages"][0]["role"], "user")
        self.assertEqual(json_body["messages"][0]["content"], [{"type": "text", "text": "Hello World"}])

    def test_openai_payload_with_image_and_api_key(self):
        url, headers, json_body = _prepare_rest_payload(
            provider="  vllm ",
            model="llama-3",
            prompt="Describe this image",
            img_base64="somebase64string",
            text_content="Extra text details",
            api_key="my-key",
            endpoint="http://localhost:8000/",
        )
        self.assertEqual(url, "http://localhost:8000/chat/completions")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Authorization"], "Bearer my-key")
        self.assertEqual(json_body["model"], "llama-3")
        self.assertEqual(json_body["stream"], False)

        expected_prompt = "Describe this image\n\n[Content]\nExtra text details"
        content_list = json_body["messages"][0]["content"]
        self.assertEqual(len(content_list), 2)
        self.assertEqual(content_list[0], {"type": "text", "text": expected_prompt})
        self.assertEqual(content_list[1], {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,somebase64string"}
        })

    def test_anthropic_payload_with_image(self):
        url, headers, json_body = _prepare_rest_payload(
            provider="Anthropic",
            model="claude-3",
            prompt="Describe",
            img_base64="anotherbase64",
            text_content=None,
            api_key="anthropic-key",
            endpoint="https://api.anthropic.com/",
        )
        self.assertEqual(url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["x-api-key"], "anthropic-key")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertEqual(json_body["model"], "claude-3")
        self.assertEqual(json_body["max_tokens"], 1024)

        content_list = json_body["messages"][0]["content"]
        self.assertEqual(len(content_list), 2)
        self.assertEqual(content_list[0], {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": "anotherbase64",
            }
        })
        self.assertEqual(content_list[1], {"type": "text", "text": "Describe"})

    def test_anthropic_payload_no_image(self):
        url, headers, json_body = _prepare_rest_payload(
            provider="anthropic",
            model="claude-3",
            prompt="Summarize",
            img_base64=None,
            text_content="Document text",
            api_key="anthropic-key",
            endpoint="https://api.anthropic.com",
        )
        self.assertEqual(url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(json_body["max_tokens"], 1024)

        expected_prompt = "Summarize\n\n[Content]\nDocument text"
        content_list = json_body["messages"][0]["content"]
        self.assertEqual(len(content_list), 1)
        self.assertEqual(content_list[0], {"type": "text", "text": expected_prompt})

    def test_google_gemini_payload_with_image(self):
        url, headers, json_body = _prepare_rest_payload(
            provider="gEmInI",
            model="gemini-pro",
            prompt="Look at this",
            img_base64="geminibase64",
            text_content=None,
            api_key="gemini-key",
            endpoint="https://generativelanguage.googleapis.com",
        )
        expected_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        self.assertEqual(url, expected_url)
        self.assertEqual(headers["x-goog-api-key"], "gemini-key")

        parts = json_body["contents"][0]["parts"]
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], {"text": "Look at this"})
        self.assertEqual(parts[1], {
            "inlineData": {
                "mimeType": "image/png",
                "data": "geminibase64",
            }
        })

    def test_google_gemini_payload_no_image(self):
        url, headers, json_body = _prepare_rest_payload(
            provider="google",
            model="gemini-pro",
            prompt="Analyze",
            img_base64=None,
            text_content="Some code snippet",
            api_key="gemini-key",
            endpoint="https://generativelanguage.googleapis.com/",
        )
        expected_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        self.assertEqual(url, expected_url)
        self.assertEqual(headers["x-goog-api-key"], "gemini-key")

        parts = json_body["contents"][0]["parts"]
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0], {"text": "Analyze\n\n[Content]\nSome code snippet"})

    def test_ollama_fallback_payload_with_image(self):
        url, headers, json_body = _prepare_rest_payload(
            provider="ollama",
            model="qwen",
            prompt="Describe this chart",
            img_base64="ollamabase64",
            text_content=None,
            api_key="",
            endpoint="http://localhost:11434",
        )
        self.assertEqual(url, "http://localhost:11434/api/chat")
        self.assertEqual(headers, {"Content-Type": "application/json"})
        self.assertEqual(json_body["model"], "qwen")
        self.assertEqual(json_body["stream"], False)

        messages = json_body["messages"]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "Describe this chart")
        self.assertEqual(messages[0]["images"], ["ollamabase64"])

    def test_ollama_fallback_payload_no_image(self):
        url, headers, json_body = _prepare_rest_payload(
            provider="something_unknown",
            model="local-model",
            prompt="Query text",
            img_base64=None,
            text_content="Context text",
            api_key="",
            endpoint="http://localhost:11434/",
        )
        self.assertEqual(url, "http://localhost:11434/api/chat")

        messages = json_body["messages"]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "Query text\n\n[Content]\nContext text")
        self.assertNotIn("images", messages[0])

if __name__ == "__main__":
    unittest.main()
