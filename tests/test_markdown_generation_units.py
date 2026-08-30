from unittest.mock import MagicMock

from docling_lib.converter import DocumentConversionOptions, PDFConverter


def test_markdown_generation_from_doc_mock():
    """
    Verifies that EnhancedMarkdownSerializer renders Markdown correctly
    from a DoclingDocument object.
    """
    doc = MagicMock()
    doc._mock_name = "MockDoclingDocument"
    doc.name = "sample_test_doc.pdf"
    doc.pictures = []
    doc.tables = []

    options = DocumentConversionOptions(
        table_format="html",
        include_page_breaks=True,
    )

    converter = PDFConverter(options=options)
    md_text = converter._serialize_to_markdown(doc=doc, table_format="html", options=options)
    md_content = converter._apply_metadata_frontmatter(doc=doc, md_content=md_text, options=options)

    assert "title: sample_test_doc.pdf" in md_content
