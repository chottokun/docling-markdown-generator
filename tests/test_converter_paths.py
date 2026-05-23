import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docling_lib.converter import PDFConverter


def test_validate_and_resolve_paths_exception_handling(caplog):
    """
    Test that _validate_and_resolve_paths logs an error and re-raises
    when an unexpected exception occurs during path resolution.
    """
    converter = PDFConverter()
    output_dir = Path("/fake/output")

    # We want to mock Path.resolve() to raise an exception.
    # Since _validate_and_resolve_paths uses output_dir.resolve(),
    # we can mock the resolve method of the output_dir object.

    with patch.object(Path, "resolve", side_effect=Exception("Simulated resolution error")):
        with pytest.raises(Exception, match="Simulated resolution error"):
            with caplog.at_level(logging.ERROR):
                converter._validate_and_resolve_paths(
                    output_dir=output_dir,
                    image_dir_name="images",
                    md_output_name="output.md"
                )

    assert "Security Error during path resolution: Simulated resolution error" in caplog.text


def test_validate_and_resolve_paths_traversal_logging_image_dir(caplog):
    """
    Test that _validate_and_resolve_paths logs a specific security error
    when image directory traversal is detected.
    """
    converter = PDFConverter()
    # Using a real tmp_path to ensure is_relative_to works correctly
    output_dir = Path("/tmp/base")
    image_dir_name = "../traversal_images"
    md_output_name = "safe.md"

    # Mocking resolve to return specific paths that trigger traversal detection
    # resolved_output_dir = output_dir.resolve()
    # resolved_images_dir = (output_dir / image_dir_name).resolve()

    with patch.object(Path, "resolve") as mock_resolve:
        # First call for output_dir.resolve()
        # Second call for (output_dir / image_dir_name).resolve()
        # Third call for (output_dir / md_output_name).resolve()

        mock_resolve.side_effect = [
            Path("/tmp/base"),            # output_dir.resolve()
            Path("/tmp/traversal_images"), # images_dir.resolve()
            Path("/tmp/base/safe.md")     # md_path.resolve()
        ]

        with pytest.raises(ValueError, match="Traversal detected in image directory"):
            with caplog.at_level(logging.ERROR):
                converter._validate_and_resolve_paths(
                    output_dir=output_dir,
                    image_dir_name=image_dir_name,
                    md_output_name=md_output_name
                )

    assert "Security Error: Traversal detected in image directory ../traversal_images" in caplog.text


def test_validate_and_resolve_paths_traversal_logging_markdown_path(caplog):
    """
    Test that _validate_and_resolve_paths logs a specific security error
    when markdown output path traversal is detected.
    """
    converter = PDFConverter()
    output_dir = Path("/tmp/base")
    image_dir_name = "images"
    md_output_name = "../traversal.md"

    with patch.object(Path, "resolve") as mock_resolve:
        mock_resolve.side_effect = [
            Path("/tmp/base"),            # output_dir.resolve()
            Path("/tmp/base/images"),     # images_dir.resolve()
            Path("/tmp/traversal.md")     # md_path.resolve()
        ]

        with pytest.raises(ValueError, match="Traversal detected in markdown output name"):
            with caplog.at_level(logging.ERROR):
                converter._validate_and_resolve_paths(
                    output_dir=output_dir,
                    image_dir_name=image_dir_name,
                    md_output_name=md_output_name
                )

    assert "Security Error: Traversal detected in markdown output name ../traversal.md" in caplog.text
