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


def test_apply_metadata_frontmatter_generic_exception(tmp_path, caplog):
    """Test that a generic Exception in _apply_metadata_frontmatter is caught and returns None."""
    import logging
    from unittest.mock import MagicMock, patch

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
            with patch.object(converter, "_apply_metadata_frontmatter", side_effect=ValueError("Simulated Frontmatter Error")):
                with caplog.at_level(logging.ERROR):
                    result = converter.convert(input_path, output_dir)

    assert result is None
    assert "Error converting document" in caplog.text
    assert "Simulated Frontmatter Error" in caplog.text


def test_apply_metadata_frontmatter_os_error_propagation(tmp_path):
    """Test that OSError in _apply_metadata_frontmatter is propagated to the caller."""
    import pytest
    from unittest.mock import MagicMock, patch

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
            with patch.object(converter, "_apply_metadata_frontmatter", side_effect=OSError("Simulated Frontmatter OSError")):
                with pytest.raises(OSError, match="Simulated Frontmatter OSError"):
                    converter.convert(input_path, output_dir)


def test_apply_metadata_frontmatter_permission_error_propagation(tmp_path):
    """Test that PermissionError in _apply_metadata_frontmatter is propagated to the caller."""
    import pytest
    from unittest.mock import MagicMock, patch

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
            with patch.object(converter, "_apply_metadata_frontmatter", side_effect=PermissionError("Simulated Frontmatter PermissionError")):
                with pytest.raises(PermissionError, match="Simulated Frontmatter PermissionError"):
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
