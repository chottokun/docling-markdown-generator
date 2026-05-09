from unittest.mock import MagicMock, patch

import pytest

from docling_lib.converter import DocumentConversionOptions, PDFConverter


def test_save_markdown_path_traversal_vulnerability(tmp_path):
    """
    Test that demonstrates the path traversal vulnerability in _save_markdown.
    If vulnerable, it will write a file outside the intended output directory.
    """
    # Setup
    # Malicious names
    malicious_md_name = "../traversal_md.md"
    malicious_image_dir = "../traversal_images"

    options = DocumentConversionOptions(
        md_output_name=malicious_md_name, image_dir_name=malicious_image_dir
    )
    converter = PDFConverter(options=options)

    # Mock DoclingDocument
    doc = MagicMock()
    doc.name = "test_doc"

    # Mock EnhancedMarkdownSerializer to avoid real serialization
    with patch("docling_lib.converter.EnhancedMarkdownSerializer") as MockSerializer:
        mock_instance = MockSerializer.return_value
        mock_instance.serialize.return_value.text = "# Mock Markdown Content"

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Call the vulnerable method and expect it to raise ValueError due to protection
        with pytest.raises(ValueError, match="Traversal detected"):
            converter._save_markdown(
                doc=doc,
                output_dir=output_dir,
            )

        # Verify that no files were created outside the output directory
        traversal_md_file = tmp_path / "traversal_md.md"
        traversal_image_dir = tmp_path / "traversal_images"

        assert not traversal_md_file.exists(), (
            "Vulnerability: Markdown file written outside output_dir!"
        )
        assert not traversal_image_dir.exists(), (
            "Vulnerability: Image directory created outside output_dir!"
        )


def test_save_markdown_image_dir_traversal(tmp_path):
    """
    Specifically test if image_dir_name can cause traversal.
    """
    malicious_image_dir = "../../malicious_images"
    options = DocumentConversionOptions(
        image_dir_name=malicious_image_dir, md_output_name="safe.md"
    )
    converter = PDFConverter(options=options)
    doc = MagicMock()
    doc.name = "test_doc"

    with patch("docling_lib.converter.EnhancedMarkdownSerializer") as MockSerializer:
        MockSerializer.return_value.serialize.return_value.text = "content"

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(ValueError, match="Traversal detected"):
            converter._save_markdown(
                doc=doc,
                output_dir=output_dir,
            )

        traversal_image_dir = tmp_path.parent / "malicious_images"
        assert not traversal_image_dir.exists(), (
            "Vulnerability: Image directory created with traversal!"
        )
