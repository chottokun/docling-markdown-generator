import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock docling and torch before importing PDFConverter
from tests.mock_docling import mock_docling

mock_docling()

from PIL import Image
from docling_core.types.doc import (
    DoclingDocument,
    ImageRef,
    PictureItem,
    Size,
    ImageRefMode,
)

from docling_core.transforms.serializer.markdown import MarkdownParams
from docling_lib.converter import (
    DocumentConversionOptions,
    EnhancedMarkdownSerializer,
    PDFConverter,
    CustomMarkdownPictureSerializer,
)
from docling_lib.vlm import generate_caption, generate_caption_sync


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

        with patch("docling_core.transforms.serializer.markdown.MarkdownPictureSerializer._serialize_image_part") as mock_super_img:
            from docling_core.transforms.serializer.markdown import create_ser_result
            mock_super_img.return_value = create_ser_result(text="![Image](http://example.com/pic.png)", span_source=pic_item)

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
            model="qwen2-vl:2b",
            endpoint="http://localhost:11434",
            prompt="画像の説明をして",
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
        parts = [create_ser_result(text="# Page 1\n#_#_DOCLING_DOC_PAGE_BREAK_1_2_#_#\n# Page 2")]
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


if __name__ == "__main__":
    unittest.main()
