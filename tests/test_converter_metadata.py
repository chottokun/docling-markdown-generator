from docling_core.types.doc import DoclingDocument

from docling_lib.converter import PDFConverter


def test_apply_metadata_frontmatter_with_name():
    """Test that frontmatter is added when doc.name is present."""
    converter = PDFConverter()
    doc = DoclingDocument(name="Test Document")
    md_content = "This is the content."

    result = converter._apply_metadata_frontmatter(doc, md_content)

    expected = "---\ntitle: Test Document\n---\n\nThis is the content."
    assert result == expected


def test_apply_metadata_frontmatter_with_empty_name():
    """Test that frontmatter is not added when doc.name is an empty string."""
    converter = PDFConverter()
    doc = DoclingDocument(name="")
    md_content = "This is the content."

    result = converter._apply_metadata_frontmatter(doc, md_content)

    assert result == md_content


def test_apply_metadata_frontmatter_with_none_name():
    """Test that frontmatter is not added when doc.name is None."""
    converter = PDFConverter()

    # Use a mock to simulate doc.name being None,
    # since DoclingDocument validation might require a string.
    from unittest.mock import MagicMock

    doc = MagicMock(spec=DoclingDocument)
    doc.name = None
    md_content = "This is the content."

    result = converter._apply_metadata_frontmatter(doc, md_content)

    assert result == md_content
