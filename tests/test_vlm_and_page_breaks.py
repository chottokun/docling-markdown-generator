import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.mock_docling import mock_docling

mock_docling()

from docling_core.transforms.serializer.markdown import MarkdownParams
from docling_core.types.doc import (
    DoclingDocument,
    ImageRef,
    ImageRefMode,
    PictureItem,
    Size,
)
from PIL import Image

from docling_lib.converter import (
    CustomMarkdownPictureSerializer,
    DocumentConversionOptions,
    EnhancedMarkdownSerializer,
    PDFConverter,
)
from docling_lib.vlm import generate_caption_sync


class TestVLMAndPageBreaks(unittest.TestCase):
    @patch("httpx.Client")
    def test_vlm_sync_client_success(self, mock_client_cls):
        # Setup mock client
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "富士山の写真です。"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        # Call generate_caption_sync
        img = Image.new("RGB", (100, 100))
        result = generate_caption_sync(
            img,
            model="qwen2-vl:2b",
            endpoint="http://localhost:11434",
            prompt="Describe",
        )

        # Assert
        self.assertEqual(result, "富士山の写真です。")
        mock_client.post.assert_called_once()

    @patch("httpx.Client")
    def test_vlm_sync_client_failure(self, mock_client_cls):
        # Setup mock client to throw exception
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.side_effect = Exception("Ollama is down")

        # Call generate_caption_sync
        img = Image.new("RGB", (100, 100))
        result = generate_caption_sync(img)

        # Assert (should not raise exception, but return empty string)
        self.assertEqual(result, "")

    @patch("docling_lib.vlm.generate_caption_sync")
    def test_custom_picture_serializer_with_vlm(self, mock_caption_sync):
        mock_caption_sync.return_value = "これは綺麗なチャートです。"

        # Setup custom picture serializer with VLM enabled
        pic_serializer = CustomMarkdownPictureSerializer(
            vlm_enabled=True,
            vlm_model="qwen2-vl:2b",
            vlm_endpoint="http://localhost:11434",
            vlm_prompt="画像の説明をして",
        )

        img_ref = ImageRef(
            mimetype="image/png",
            dpi=72,
            size=Size(width=50.0, height=50.0),
            uri="http://example.com/pic.png",
        )
        object.__setattr__(img_ref, "_pil", Image.new("RGB", (50, 50)))

        pic_item = PictureItem(self_ref="#/body/0", image=img_ref)

        # Mock dependencies for serialize
        doc_serializer = MagicMock()
        # Mock captions serialize
        doc_serializer.serialize_captions.return_value.text = "Caption Text"
        doc_serializer.get_excluded_refs.return_value = set()
        doc_serializer.serialize_annotations.return_value.text = ""

        doc = MagicMock(spec=DoclingDocument)

        with patch(
            "docling_core.transforms.serializer.markdown.MarkdownPictureSerializer._serialize_image_part"
        ) as mock_super_img:
            from docling_core.transforms.serializer.markdown import create_ser_result

            mock_super_img.return_value = create_ser_result(
                text="![Image](http://example.com/pic.png)", span_source=pic_item
            )

            res = pic_serializer.serialize(
                item=pic_item,
                doc_serializer=doc_serializer,
                doc=doc,
            )

        # Assert caption was generated and appended using markers
        self.assertIn("<!-- VLM_CAPTION_START -->", res.text)
        self.assertIn("これは綺麗なチャートです。", res.text)
        self.assertIn("<!-- VLM_CAPTION_END -->", res.text)
        mock_caption_sync.assert_called_once_with(
            image=pic_item.image.pil_image,
            provider="ollama",
            api_key="",
            model="qwen2-vl:2b",
            endpoint="http://localhost:11434",
            prompt="画像の説明をして",
            vlm_max_concurrent=5,
        )

    def test_page_break_rendering_direct(self):
        # Instantiate real EnhancedMarkdownSerializer with mock doc
        doc = MagicMock()
        serializer = EnhancedMarkdownSerializer(
            doc=doc,
            table_format="html",
            vlm_enabled=False,
            params=MarkdownParams(
                image_mode=ImageRefMode.REFERENCED,
                page_break_placeholder="<!-- PAGE_BREAK_MARKER -->",
            ),
        )

        # Call serialize_doc with a mocked SerializationResult containing raw page break
        from docling_core.transforms.serializer.markdown import create_ser_result

        parts = [
            create_ser_result(
                text="# Page 1\n#_#_DOCLING_DOC_PAGE_BREAK_1_2_#_#\n# Page 2"
            )
        ]
        res = serializer.serialize_doc(parts=parts)

        # Assert
        self.assertIn("<!-- PAGE_BREAK: Page 2 -->", res.text)
        self.assertNotIn("#_#_DOCLING_DOC_PAGE_BREAK_", res.text)

    def test_page_break_prepending(self):
        options = DocumentConversionOptions(include_page_breaks=True)
        converter = PDFConverter(options=options)

        doc = MagicMock()
        doc.name = "Test Document"
        doc.pictures = []

        # We want to check that _save_markdown prepends <!-- PAGE_BREAK: Page 1 -->
        # We can mock _serialize_to_markdown to return some text
        with patch.object(converter, "_serialize_to_markdown") as mock_serialize:
            mock_serialize.return_value = "# Page 1 Content"
            with patch("pathlib.Path.write_text") as mock_write:
                converter._save_markdown(doc, output_dir=Path("images_dir"))

        written_content = mock_write.call_args[0][0]
        # Assert YAML frontmatter block is still at absolute top, but page break is in written content
        self.assertTrue(written_content.startswith("---\ntitle: Test Document\n---"))
        self.assertIn("<!-- PAGE_BREAK: Page 1 -->", written_content)

    def test_table_format_toggle_markdown(self):
        # Test table format set to markdown
        options = DocumentConversionOptions(table_format="markdown")
        serializer = EnhancedMarkdownSerializer(
            doc=DoclingDocument(name="test"), table_format=options.table_format
        )

        from docling_core.transforms.serializer.markdown import (
            MarkdownTableSerializer,
        )

        self.assertIsInstance(serializer.table_serializer, MarkdownTableSerializer)
        self.assertNotEqual(
            serializer.table_serializer.__class__.__name__,
            "HTMLTableMarkdownSerializer",
        )

    def test_table_format_toggle_html(self):
        # Test table format set to html (default)
        options = DocumentConversionOptions(table_format="html")
        serializer = EnhancedMarkdownSerializer(
            doc=DoclingDocument(name="test"), table_format=options.table_format
        )

        self.assertEqual(
            serializer.table_serializer.__class__.__name__,
            "HTMLTableMarkdownSerializer",
        )

    @patch("docling_lib.vlm.generate_caption_sync")
    def test_vlm_prefetch(self, mock_caption_sync):
        mock_caption_sync.return_value = "Prefetched Caption!"

        converter = PDFConverter()
        options = DocumentConversionOptions(
            vlm_enabled=True,
            vlm_model="qwen2-vl:2b",
            vlm_endpoint="http://localhost:11434",
            vlm_prompt="Prefetch prompt",
        )

        # Mock DoclingDocument containing pictures
        img_ref = ImageRef(
            mimetype="image/png",
            dpi=72,
            size=Size(width=50.0, height=50.0),
            uri="http://example.com/pic.png",
        )
        object.__setattr__(img_ref, "_pil", Image.new("RGB", (50, 50)))
        pic_item = PictureItem(self_ref="#/body/0", image=img_ref)

        doc = MagicMock(spec=DoclingDocument)
        doc.pictures = [pic_item]

        # Call _prefetch_vlm_captions
        captions = converter._prefetch_vlm_captions(doc, options)

        # Assert
        self.assertEqual(captions, {"#/body/0": "Prefetched Caption!"})
        mock_caption_sync.assert_called_once_with(
            image=pic_item.image.pil_image,
            provider="ollama",
            api_key="",
            model="qwen2-vl:2b",
            endpoint="http://localhost:11434",
            prompt="Prefetch prompt",
            vlm_max_concurrent=5,
        )

    @patch("docling_lib.vlm.generate_caption_sync")
    def test_vlm_prefetch_partial_failure(self, mock_caption_sync):
        # Setup mock side effect: simulate that image with size (10, 10) causes VLM timeout
        def side_effect(image, **kwargs):
            if image.size == (10, 10):
                raise ValueError("VLM connection timeout")
            return "Good Caption"

        mock_caption_sync.side_effect = side_effect

        converter = PDFConverter()
        options = DocumentConversionOptions(
            vlm_enabled=True,
            vlm_model="qwen2-vl:2b",
            vlm_endpoint="http://localhost:11434",
            vlm_prompt="Describe",
        )

        # 1st image: Normal
        img_ref1 = ImageRef(
            mimetype="image/png", dpi=72, size=Size(width=50.0, height=50.0), uri="1"
        )
        object.__setattr__(img_ref1, "_pil", Image.new("RGB", (50, 50)))
        pic_item1 = PictureItem(self_ref="#/body/0", image=img_ref1)

        # 2nd image: Error-triggering size (10, 10)
        img_ref_err = ImageRef(
            mimetype="image/png", dpi=72, size=Size(width=10.0, height=10.0), uri="err"
        )
        object.__setattr__(img_ref_err, "_pil", Image.new("RGB", (10, 10)))
        pic_item_err = PictureItem(self_ref="#/body/1", image=img_ref_err)

        doc = MagicMock(spec=DoclingDocument)
        doc.pictures = [pic_item1, pic_item_err]

        # Call prefetch: should run successfully, skipping the failed image without crash
        captions = converter._prefetch_vlm_captions(doc, options)

        # Assert: only the successful caption is returned
        self.assertEqual(captions, {"#/body/0": "Good Caption"})

    def test_vlm_prefetch_invalid_images(self):
        converter = PDFConverter()
        options = DocumentConversionOptions(vlm_enabled=True)

        # 1. Pictures list is empty
        doc = MagicMock(spec=DoclingDocument)
        doc.pictures = []
        captions = converter._prefetch_vlm_captions(doc, options)
        self.assertEqual(captions, {})

        # 2. Image reference or pil_image is None
        pic_item_no_img = PictureItem(self_ref="#/body/0", image=None)

        img_ref_no_pil = ImageRef(
            mimetype="image/png", dpi=72, size=Size(width=50.0, height=50.0), uri="3"
        )
        pic_item_no_pil = PictureItem(self_ref="#/body/1", image=img_ref_no_pil)

        doc.pictures = [pic_item_no_img, pic_item_no_pil]
        captions = converter._prefetch_vlm_captions(doc, options)
        self.assertEqual(captions, {})

    @patch("httpx.Client")
    def test_vlm_api_unexpected_response(self, mock_client_cls):
        mock_client = mock_client_cls.return_value.__enter__.return_value

        # Ollama API returns 200 OK but with unexpected JSON schema
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "error": "Model not found"
        }  # Key "message" is missing
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        img = Image.new("RGB", (10, 10))
        result = generate_caption_sync(img)

        # Must fall back to empty string without raising KeyError/AttributeError
        self.assertEqual(result, "")

    @unittest.skipIf(
        os.getenv("DOCLING_RUN_E2E") != "true",
        "Skipping Ollama VLM integration test because DOCLING_RUN_E2E is not set to true",
    )
    def test_actual_ollama_vlm_integration(self):
        """
        Integration test that calls the actual local Ollama service if running.
        If Ollama is not running, the test is skipped automatically.
        """
        # Force stop active patches to allow actual HTTP requests during this test
        patch.stopall()

        import httpx

        try:
            # Check if local Ollama is up and has models
            res = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
            if res.status_code != 200:
                self.skipTest("Ollama is not running on localhost:11434")
            models = [m["name"] for m in res.json().get("models", [])]
            # Use qwen3.5:4b which we verified works
            target_model = None
            for m in ["qwen3.5:4b", "qwen3.5:latest"]:
                if m in models:
                    target_model = m
                    break
            if not target_model:
                self.skipTest(
                    "No compatible qwen3.5 model is available in local Ollama"
                )
        except Exception:
            self.skipTest("Ollama is not reachable")

        # Call the real VLM API
        img = Image.new("RGB", (100, 100), color="blue")
        caption = generate_caption_sync(
            image=img,
            model=target_model,
            endpoint="http://localhost:11434",
            prompt="この画像の色は何ですか？単語だけで答えてください。",
        )
        # Verify we got a valid response containing '青'
        self.assertTrue(len(caption) > 0)
        self.assertIn("青", caption)


if __name__ == "__main__":
    unittest.main()
