import logging
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from docling_lib.converter import PDFConverter, DocumentConversionOptions

def test_validate_and_resolve_paths_success(tmp_path):
    """Verify that valid paths are resolved correctly."""
    converter = PDFConverter()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    image_dir_name = "images"
    md_output_name = "output.md"

    resolved_images, resolved_md = converter._validate_and_resolve_paths(
        output_dir, image_dir_name, md_output_name
    )

    assert resolved_images == (output_dir / image_dir_name).resolve()
    assert resolved_md == (output_dir / md_output_name).resolve()

def test_validate_and_resolve_paths_traversal_images(tmp_path):
    """Verify that traversal in images directory is detected."""
    converter = PDFConverter()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    image_dir_name = "../outside_images"
    md_output_name = "output.md"

    with pytest.raises(ValueError, match="Traversal detected in image directory"):
        converter._validate_and_resolve_paths(output_dir, image_dir_name, md_output_name)

def test_validate_and_resolve_paths_traversal_md(tmp_path):
    """Verify that traversal in markdown output name is detected."""
    converter = PDFConverter()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    image_dir_name = "images"
    md_output_name = "../outside.md"

    with pytest.raises(ValueError, match="Traversal detected in markdown output name"):
        converter._validate_and_resolve_paths(output_dir, image_dir_name, md_output_name)

def test_validate_and_resolve_paths_exception(tmp_path, caplog):
    """Verify handling of unexpected exceptions during path resolution."""
    converter = PDFConverter()
    output_dir = tmp_path / "output"
    # We don't need to create it if we're mocking resolve

    with patch("docling_lib.converter.Path.resolve", side_effect=RuntimeError("Unexpected resolution error")):
        with caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError, match="Unexpected resolution error"):
                converter._validate_and_resolve_paths(output_dir, "images", "out.md")

            assert "Security Error during path resolution: Unexpected resolution error" in caplog.text
