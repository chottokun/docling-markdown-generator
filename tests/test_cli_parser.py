import pytest
from pathlib import Path
from tests.mock_docling import mock_docling

# Call mock_docling before importing cli to handle missing dependencies
mock_docling()

from docling_lib.cli import setup_parser
from docling_lib.config import IMAGE_DIR_NAME, IMAGE_RESOLUTION_SCALE, MD_OUTPUT_NAME

def test_setup_parser_defaults():
    """Test that setup_parser returns a parser with expected default values."""
    parser = setup_parser()
    # Required argument 'pdf_file' must be provided to parse_args
    args = parser.parse_args(["test.pdf"])

    assert args.pdf_file == Path("test.pdf")
    assert args.output_dir == Path("output")
    assert args.image_dir == IMAGE_DIR_NAME
    assert args.output_name == MD_OUTPUT_NAME
    assert args.image_scale == IMAGE_RESOLUTION_SCALE

def test_setup_parser_custom_values():
    """Test that setup_parser correctly handles custom argument values."""
    parser = setup_parser()
    args = parser.parse_args([
        "input.pdf",
        "--output-dir", "custom_out",
        "--image-dir", "custom_images",
        "--output-name", "custom.md",
        "--image-scale", "3.5"
    ])

    assert args.pdf_file == Path("input.pdf")
    assert args.output_dir == Path("custom_out")
    assert args.image_dir == "custom_images"
    assert args.output_name == "custom.md"
    assert args.image_scale == 3.5

def test_setup_parser_short_flags():
    """Test that setup_parser correctly handles short flags."""
    parser = setup_parser()
    args = parser.parse_args([
        "input.pdf",
        "-o", "short_out",
        "-n", "short.md",
        "-s", "1.5"
    ])

    assert args.output_dir == Path("short_out")
    assert args.output_name == "short.md"
    assert args.image_scale == 1.5

def test_setup_parser_missing_required():
    """Test that setup_parser raises SystemExit when required arguments are missing."""
    parser = setup_parser()
    with pytest.raises(SystemExit):
        # Missing 'pdf_file'
        parser.parse_args([])

def test_setup_parser_invalid_scale():
    """Test that setup_parser raises SystemExit for invalid scale type."""
    parser = setup_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["test.pdf", "--image-scale", "not-a-number"])

def test_setup_parser_path_conversion():
    """Test that setup_parser correctly converts string arguments to Path objects."""
    parser = setup_parser()
    args = parser.parse_args(["path/to/file.pdf", "-o", "another/path"])

    assert isinstance(args.pdf_file, Path)
    assert isinstance(args.output_dir, Path)
    assert args.pdf_file == Path("path/to/file.pdf")
    assert args.output_dir == Path("another/path")
