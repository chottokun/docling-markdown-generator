import logging
from unittest.mock import MagicMock, patch

import pytest
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


def test_apply_metadata_frontmatter_with_page_count():
    """Test that frontmatter includes page count when doc has a positive page count."""
    converter = PDFConverter()
    doc = MagicMock(spec=DoclingDocument)
    doc.name = "Page Count Doc"
    doc.num_pages.return_value = 5
    md_content = "This is the content."

    result = converter._apply_metadata_frontmatter(doc, md_content)

    # Use a multiline expected string with correct indentation and format
    expected = "---\npage_count: 5\ntitle: Page Count Doc\n---\n\nThis is the content."
    assert result == expected


def test_apply_metadata_frontmatter_with_zero_or_negative_page_count():
    """Test that frontmatter does not include page count when doc has zero or negative pages."""
    converter = PDFConverter()
    doc = MagicMock(spec=DoclingDocument)
    doc.name = "Zero Page Doc"
    doc.num_pages.return_value = 0
    md_content = "This is the content."

    result = converter._apply_metadata_frontmatter(doc, md_content)

    expected = "---\ntitle: Zero Page Doc\n---\n\nThis is the content."
    assert result == expected


def test_apply_metadata_frontmatter_without_num_pages():
    """Test that frontmatter is generated safely when doc lacks a num_pages method."""
    converter = PDFConverter()

    class MockDocWithNoNumPages:
        name = "No Num Pages Doc"

    doc = MockDocWithNoNumPages()
    md_content = "This is the content."

    result = converter._apply_metadata_frontmatter(doc, md_content)

    expected = "---\ntitle: No Num Pages Doc\n---\n\nThis is the content."
    assert result == expected


def test_apply_metadata_frontmatter_num_pages_exception(caplog):
    """Test that exceptions during num_pages() call are caught and logged."""
    converter = PDFConverter()
    doc = MagicMock(spec=DoclingDocument)
    doc.name = "Exception Doc"
    doc.num_pages.side_effect = ValueError("Failed to count pages")
    md_content = "This is the content."

    result = converter._apply_metadata_frontmatter(doc, md_content)

    # page_count should be ignored, title should still be included, and warning logged
    expected = "---\ntitle: Exception Doc\n---\n\nThis is the content."
    assert result == expected
    assert "Failed to extract page count" in caplog.text


def test_apply_metadata_frontmatter_generic_exception(tmp_path, caplog):
    """Test that a generic Exception in _apply_metadata_frontmatter is caught and returns None."""
    converter = PDFConverter()
    input_path = tmp_path / "test.pdf"
    input_path.touch()
    output_dir = tmp_path / "output"

    # Mock convert to trigger _save_markdown, but mock _apply_metadata_frontmatter to crash
    mock_doc = MagicMock(spec=DoclingDocument)
    mock_doc.name = "Test Document"
    mock_doc.pictures = []

    with patch.object(converter.doc_converter, "convert") as mock_convert:
        mock_convert.return_value.document = mock_doc
        with patch.object(converter, "_serialize_to_markdown", return_value="# Title"):
            with patch.object(
                converter,
                "_apply_metadata_frontmatter",
                side_effect=ValueError("Simulated Frontmatter Error"),
            ):
                with caplog.at_level(logging.ERROR):
                    result = converter.convert(input_path, output_dir)

    assert result is None
    assert "Error converting document" in caplog.text
    assert "Simulated Frontmatter Error" in caplog.text


def test_apply_metadata_frontmatter_os_error_propagation(tmp_path):
    """Test that OSError in _apply_metadata_frontmatter is propagated to the caller."""
    converter = PDFConverter()
    input_path = tmp_path / "test.pdf"
    input_path.touch()
    output_dir = tmp_path / "output"

    mock_doc = MagicMock(spec=DoclingDocument)
    mock_doc.name = "Test Document"
    mock_doc.pictures = []

    with patch.object(converter.doc_converter, "convert") as mock_convert:
        mock_convert.return_value.document = mock_doc
        with patch.object(converter, "_serialize_to_markdown", return_value="# Title"):
            with patch.object(
                converter,
                "_apply_metadata_frontmatter",
                side_effect=OSError("Simulated Frontmatter OSError"),
            ):
                with pytest.raises(OSError, match="Simulated Frontmatter OSError"):
                    converter.convert(input_path, output_dir)


def test_apply_metadata_frontmatter_permission_error_propagation(tmp_path):
    """Test that PermissionError in _apply_metadata_frontmatter is propagated to the caller."""
    converter = PDFConverter()
    input_path = tmp_path / "test.pdf"
    input_path.touch()
    output_dir = tmp_path / "output"

    mock_doc = MagicMock(spec=DoclingDocument)
    mock_doc.name = "Test Document"
    mock_doc.pictures = []

    with patch.object(converter.doc_converter, "convert") as mock_convert:
        mock_convert.return_value.document = mock_doc
        with patch.object(converter, "_serialize_to_markdown", return_value="# Title"):
            with patch.object(
                converter,
                "_apply_metadata_frontmatter",
                side_effect=PermissionError("Simulated Frontmatter PermissionError"),
            ):
                with pytest.raises(
                    PermissionError, match="Simulated Frontmatter PermissionError"
                ):
                    converter.convert(input_path, output_dir)


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
