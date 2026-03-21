from unittest.mock import MagicMock, patch

from docling_lib.converter import PDFConverter


def test_save_markdown_path_traversal_vulnerability(tmp_path):
    """
    Test that demonstrates the path traversal vulnerability in _save_markdown.
    If vulnerable, it will write a file outside the intended output directory.
    """
    # Setup
    converter = PDFConverter()

    # Mock DoclingDocument
    doc = MagicMock()
    doc.name = "test_doc"

    # Mock EnhancedMarkdownSerializer to avoid real serialization
    with patch('docling_lib.converter.EnhancedMarkdownSerializer') as MockSerializer:
        mock_instance = MockSerializer.return_value
        mock_instance.serialize.return_value.text = "# Mock Markdown Content"

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Malicious names
        malicious_md_name = "../traversal_md.md"
        malicious_image_dir = "../traversal_images"

        # Call the vulnerable method
        md_path = converter._save_markdown(
            doc=doc,
            output_dir=output_dir,
            image_dir_name=malicious_image_dir,
            md_output_name=malicious_md_name
        )

        # Check if the markdown file was written outside the output directory
        traversal_md_file = tmp_path / "traversal_md.md"
        traversal_image_dir = tmp_path / "traversal_images"

        # Assertions that will FAIL if the vulnerability exists
        assert not traversal_md_file.exists(), (
            "Vulnerability: Markdown file written outside output_dir!"
        )
        assert not traversal_image_dir.exists(), (
            "Vulnerability: Image directory created outside output_dir!"
        )

        # Also check md_path returned
        assert md_path.parent == output_dir.resolve(), (
            f"Returned path {md_path} is outside {output_dir}"
        )


def test_save_markdown_image_dir_traversal(tmp_path):
    """
    Specifically test if image_dir_name can cause traversal.
    """
    converter = PDFConverter()
    doc = MagicMock()
    doc.name = "test_doc"

    with patch('docling_lib.converter.EnhancedMarkdownSerializer') as MockSerializer:
        MockSerializer.return_value.serialize.return_value.text = "content"

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        malicious_image_dir = "../../malicious_images"

        converter._save_markdown(
            doc=doc,
            output_dir=output_dir,
            image_dir_name=malicious_image_dir,
            md_output_name="safe.md"
        )

        traversal_image_dir = tmp_path.parent / "malicious_images"
        assert not traversal_image_dir.exists(), (
            "Vulnerability: Image directory created with traversal!"
        )
