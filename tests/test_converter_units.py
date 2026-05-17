import logging
from unittest.mock import MagicMock, patch

import pytest

import docling_lib.converter
from docling_lib.converter import (
    DocumentConversionOptions,
    _get_or_create_converter,
    _validate_input_path,
)


@pytest.fixture(autouse=True)
def reset_default_converter():
    """Reset the global _default_pdf_converter before each test."""
    docling_lib.converter._default_pdf_converter = None
    yield
    docling_lib.converter._default_pdf_converter = None


def test_validate_input_path_exists(tmp_path):
    """Test that _validate_input_path returns True when the file exists."""
    # Setup: Create a dummy file
    test_file = tmp_path / "test.pdf"
    test_file.touch()

    # Act
    result = _validate_input_path(test_file)

    # Assert
    assert result is True


def test_validate_input_path_not_exists(tmp_path, caplog):
    """Test that _validate_input_path returns False and logs an error when the file does not exist."""
    # Setup: Path to a non-existent file
    test_file = tmp_path / "non_existent.pdf"

    # Act
    with caplog.at_level(logging.ERROR):
        result = _validate_input_path(test_file)

    # Assert
    assert result is False
    assert f"Input file not found: {test_file}" in caplog.text


def test_get_or_create_converter_initial_creation():
    """Test that _get_or_create_converter creates a new instance on first call."""
    options = DocumentConversionOptions()
    with patch("docling_lib.converter.PDFConverter") as mock_pdf_converter:
        mock_pdf_converter.return_value.options = options

        converter = _get_or_create_converter(options)

        assert converter is mock_pdf_converter.return_value
        mock_pdf_converter.assert_called_once_with(options=options)


def test_get_or_create_converter_caching():
    """Test that _get_or_create_converter returns the same instance for identical options."""
    options = DocumentConversionOptions()
    with patch("docling_lib.converter.PDFConverter") as mock_pdf_converter:
        mock_pdf_converter.return_value.options = options

        converter1 = _get_or_create_converter(options)
        converter2 = _get_or_create_converter(options)

        assert converter1 is converter2
        assert converter1 is mock_pdf_converter.return_value
        mock_pdf_converter.assert_called_once()


@pytest.mark.parametrize(
    "heavy_option_attr,new_value",
    [
        ("image_scale", 3.0),
        ("table_format", "markdown"),
        ("do_formula", not DocumentConversionOptions().do_formula),
        ("do_ocr", not DocumentConversionOptions().do_ocr),
    ],
)
def test_get_or_create_converter_reinit_on_heavy_options(heavy_option_attr, new_value):
    """Test that _get_or_create_converter re-initializes when heavy options change."""
    options1 = DocumentConversionOptions()
    options2 = DocumentConversionOptions()
    setattr(options2, heavy_option_attr, new_value)

    with patch("docling_lib.converter.PDFConverter") as mock_pdf_converter:
        mock_instance1 = MagicMock()
        mock_instance1.options = options1
        mock_instance2 = MagicMock()
        mock_instance2.options = options2

        mock_pdf_converter.side_effect = [mock_instance1, mock_instance2]

        converter1 = _get_or_create_converter(options1)
        converter2 = _get_or_create_converter(options2)

        assert converter1 is mock_instance1
        assert converter2 is mock_instance2
        assert converter1 is not converter2
        assert mock_pdf_converter.call_count == 2


def test_get_or_create_converter_no_reinit_on_light_options():
    """Test that _get_or_create_converter does NOT re-initialize when light options change."""
    options1 = DocumentConversionOptions(image_dir_name="dir1")
    options2 = DocumentConversionOptions(image_dir_name="dir2")

    with patch("docling_lib.converter.PDFConverter") as mock_pdf_converter:
        mock_instance = MagicMock()
        mock_instance.options = options1
        mock_pdf_converter.return_value = mock_instance

        converter1 = _get_or_create_converter(options1)
        converter2 = _get_or_create_converter(options2)

        assert converter1 is converter2
        assert converter1 is mock_instance
        mock_pdf_converter.assert_called_once()
