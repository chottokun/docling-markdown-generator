from unittest.mock import MagicMock, patch

from docling_lib.converter import process_pdf


def test_process_pdf_image_dir_traversal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    output_dir = tmp_path / "output"
    # Traversal in image_dir_name
    image_dir_name = "../traversal_dir"
    resolved_traversal = (output_dir / image_dir_name).resolve()

    from docling_core.types.doc import DoclingDocument
    mock_doc = MagicMock(spec=DoclingDocument)
    mock_doc.name = "test"

    # We need to mock EnhancedMarkdownSerializer to avoid pydantic errors in tests
    with patch("docling_lib.converter.DocumentConverter") as mock_conv_class, \
         patch("docling_lib.converter.EnhancedMarkdownSerializer") as mock_serializer_class:
        mock_conv = mock_conv_class.return_value
        mock_conv.convert.return_value.document = mock_doc

        mock_serializer = mock_serializer_class.return_value
        mock_serializer.serialize.return_value.text = "mocked markdown"

        result = process_pdf(pdf_path, output_dir, image_dir_name=image_dir_name)

    # process_pdf catches Exception and returns None
    assert result is None
    assert not resolved_traversal.exists(), f"Vulnerability: {resolved_traversal} was created"

def test_process_pdf_md_output_traversal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    output_dir = tmp_path / "output"
    # Traversal in md_output_name
    md_output_name = "../pwned.md"
    resolved_traversal = (output_dir / md_output_name).resolve()

    from docling_core.types.doc import DoclingDocument
    mock_doc = MagicMock(spec=DoclingDocument)
    mock_doc.name = "test"

    with patch("docling_lib.converter.DocumentConverter") as mock_conv_class, \
         patch("docling_lib.converter.EnhancedMarkdownSerializer") as mock_serializer_class:
        mock_conv = mock_conv_class.return_value
        mock_conv.convert.return_value.document = mock_doc

        mock_serializer = mock_serializer_class.return_value
        mock_serializer.serialize.return_value.text = "mocked markdown"

        result = process_pdf(pdf_path, output_dir, md_output_name=md_output_name)

    assert result is None
    assert not resolved_traversal.exists(), f"Vulnerability: {resolved_traversal} was created"
