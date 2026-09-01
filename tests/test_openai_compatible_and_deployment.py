import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from PIL import Image

from tests.mock_docling import mock_docling

mock_docling()

from docling_lib.vlm import (
    generate_caption,
    generate_caption_sync,
)


class TestOpenAICompatibleAndDeployment(unittest.IsolatedAsyncioTestCase):
    """
    OpenAI 互換推論サーバー（vLLM / llama.cpp / LM Studio 等）の動作、
    APIキー空欄時の挙動、VLM無効時の通信遮断、デプロイ構成の徹底検証。
    """

    @patch("httpx.Client")
    def test_openai_compatible_without_api_key_sync(self, mock_client_cls):
        """
        OpenAI互換サーバーでAPIキーが空欄（DOCLING_VLM_API_KEY=""）の場合、
        Authorizationヘッダーが付与されずに正常にリクエストが送信されることを検証。
        """
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"role": "assistant", "content": "Local VLM Description"}}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        img = Image.new("RGB", (20, 20))
        res = generate_caption_sync(
            image=img,
            provider="openai",
            api_key="",  # 空欄
            model="Qwen/Qwen2-VL-7B-Instruct",
            endpoint="http://localhost:8000/v1",
            prompt="画像を説明してください",
        )

        self.assertEqual(res, "Local VLM Description")
        mock_client.post.assert_called_once()
        url, kwargs = mock_client.post.call_args
        self.assertEqual(url[0], "http://localhost:8000/v1/chat/completions")
        headers = kwargs["headers"]
        # APIキーが空なので Authorization ヘッダーは存在しない
        self.assertNotIn("Authorization", headers)
        # JSON Body
        self.assertEqual(kwargs["json"]["model"], "Qwen/Qwen2-VL-7B-Instruct")

    @patch("httpx.AsyncClient")
    async def test_openai_compatible_without_api_key_async(self, mock_client_cls):
        """
        非同期版 generate_caption でもAPIキー空欄時の動作が同一であることを検証。
        """
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"role": "assistant", "content": "Async Local VLM Description"}}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post = unittest.mock.AsyncMock(return_value=mock_response)

        img = Image.new("RGB", (20, 20))
        res = await generate_caption(
            image=img,
            provider="vllm",  # vLLM 指定
            api_key="",
            model="Qwen/Qwen2-VL-7B-Instruct",
            endpoint="http://host.docker.internal:8000/v1",
            prompt="非同期テスト",
        )

        self.assertEqual(res, "Async Local VLM Description")
        url, kwargs = mock_client.post.call_args
        self.assertEqual(url[0], "http://host.docker.internal:8000/v1/chat/completions")
        self.assertNotIn("Authorization", kwargs["headers"])

    @patch("httpx.Client")
    def test_vlm_disabled_makes_zero_http_requests(self, mock_client_cls):
        """
        VLMが無効（vlm_enabled=False）のとき、画像シリアライズで
        一切の外部HTTP通信が発生しないことを検証。
        """
        mock_client = mock_client_cls.return_value.__enter__.return_value

        from docling_lib.converter import CustomMarkdownPictureSerializer

        serializer = CustomMarkdownPictureSerializer(
            vlm_enabled=False,
            vlm_provider="ollama",
            vlm_endpoint="http://localhost:11434",
            image_dir_name="images",
        )

        # モックのDoclingDocumentとPictureItemを作成
        mock_doc = MagicMock()
        mock_pic = MagicMock()
        mock_pic.self_ref = "pic_1"
        mock_pic.image.pil_image = Image.new("RGB", (10, 10))
        mock_doc.pictures = [mock_pic]

        doc_serializer = MagicMock()
        doc_serializer.serialize_captions.return_value.text = ""
        doc_serializer.get_excluded_refs.return_value = set()
        doc_serializer.serialize_annotations.return_value.text = ""

        with patch(
            "docling_core.transforms.serializer.markdown.MarkdownPictureSerializer._serialize_image_part"
        ) as mock_super_img:
            from docling_core.transforms.serializer.markdown import create_ser_result

            mock_super_img.return_value = create_ser_result(
                text="![image](images/picture_1.png)", span_source=mock_pic
            )

            # PictureItem をシリアライズ
            res = serializer.serialize(
                item=mock_pic,
                doc_serializer=doc_serializer,
                doc=mock_doc,
            )

        # HTTPリクエストが一度も呼ばれていないことを確認
        mock_client.post.assert_not_called()
        self.assertNotIn("<!-- VLM_CAPTION_START -->", res.text)
        self.assertIn("![image](images/picture_1.png)", res.text)

    def test_docker_compose_has_no_ollama_service(self):
        """
        docker-compose.yml に ollama サービスが含まれず、docling-server のみ定義されていることを検証。
        """
        compose_path = Path(__file__).resolve().parent.parent / "docker-compose.yml"
        self.assertTrue(compose_path.exists())

        with open(compose_path, encoding="utf-8") as f:
            compose_data = yaml.safe_load(f)

        services = compose_data.get("services", {})
        self.assertIn("docling-server", services)
        self.assertNotIn("ollama", services)

        volumes = compose_data.get("volumes", {})
        self.assertNotIn("ollama_data", volumes)

    def test_env_example_matches_supported_config_keys(self):
        """
        .env.example に config.py で使用されるすべての主要環境変数が網羅されているかを検証。
        """
        env_example_path = Path(__file__).resolve().parent.parent / ".env.example"
        self.assertTrue(env_example_path.exists())

        content = env_example_path.read_text(encoding="utf-8")

        required_keys = [
            "DOCLING_VLM_ENABLED",
            "DOCLING_VLM_PROVIDER",
            "DOCLING_VLM_API_KEY",
            "DOCLING_VLM_MODEL",
            "DOCLING_VLM_ENDPOINT",
            "DOCLING_VLM_PROMPT",
            "DOCLING_VLM_MAX_CONCURRENT",
            "DOCLING_API_KEY",
            "DOCLING_CORS_ORIGINS",
            "DOCLING_MAX_UPLOAD_SIZE",
            "DOCLING_RATE_LIMIT_REQUESTS",
            "DOCLING_RATE_LIMIT_WINDOW",
            "DOCLING_MAX_WORKERS",
            "DOCLING_USE_GPU",
            "DOCLING_DO_OCR",
            "DOCLING_DO_FORMULA",
            "DOCLING_DO_CHART",
            "DOCLING_DO_CODE",
            "DOCLING_TABLE_FORMAT",
            "DOCLING_INCLUDE_PAGE_BREAKS",
            "DOCLING_INCLUDE_KV_EXTRACTION",
        ]

        for key in required_keys:
            self.assertIn(key, content, f"Key {key} is missing in .env.example")


if __name__ == "__main__":
    unittest.main()
