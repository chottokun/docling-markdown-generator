
import unittest
from unittest.mock import MagicMock

# Mock docling and torch before importing PDFConverter
from tests.mock_docling import mock_docling

mock_docling()

from docling_core.types.doc import DoclingDocument

from docling_lib.converter import DocumentConversionOptions, PDFConverter


class TestRAGImprovements(unittest.TestCase):
    def setUp(self):
        self.options = DocumentConversionOptions(
            include_kv_extraction=True,
            include_page_breaks=True
        )
        self.converter = PDFConverter(options=self.options)

    def test_apply_metadata_frontmatter_rag(self):
        doc = MagicMock(spec=DoclingDocument)
        doc.name = "Test Document"
        md_content = "# Content"

        result = self.converter._apply_metadata_frontmatter(doc, md_content, self.options)

        self.assertIn("---", result)
        self.assertIn("title: Test Document", result)
        self.assertIn("## Key Information", result)
        self.assertIn("<!-- KV_START -->", result)
        self.assertIn("<!-- KV_END -->", result)

    def test_apply_metadata_frontmatter_no_rag(self):
        options = DocumentConversionOptions(include_kv_extraction=False)
        doc = MagicMock(spec=DoclingDocument)
        doc.name = "Test Document"
        md_content = "# Content"

        result = self.converter._apply_metadata_frontmatter(doc, md_content, options)

        self.assertIn("---", result)
        self.assertIn("title: Test Document", result)
        self.assertNotIn("## Key Information", result)

if __name__ == "__main__":
    unittest.main()
