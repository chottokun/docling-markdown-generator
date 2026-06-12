import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from docling_core.types.doc import DoclingDocument
from docling_lib.converter import PDFConverter, DocumentConversionOptions

def test_save_images_exception_logging(tmp_path, caplog):
    """
    Verify that an exception during image saving is caught and logged as a warning.
    """
    # Setup
    converter = PDFConverter(options=DocumentConversionOptions())
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    # Mock document with one picture that fails to save
    mock_doc = MagicMock(spec=DoclingDocument)
    mock_picture = MagicMock()
    # element.image.pil_image.save(image_path)
    mock_picture.image.pil_image.save.side_effect = Exception("Save failed\nwith newline")
    mock_doc.pictures = [mock_picture]

    # Act
    with caplog.at_level(logging.WARNING):
        converter._save_images(mock_doc, images_dir)

    # Assert
    assert "Failed to save image" in caplog.text
    # sanitize_log_message replaces \n with space
    assert "Save failed with newline" in caplog.text
    mock_picture.image.pil_image.save.assert_called_once()

def test_save_images_continues_after_failure(tmp_path, caplog):
    """
    Verify that if saving one image fails, the converter continues to subsequent images.
    """
    # Setup
    converter = PDFConverter(options=DocumentConversionOptions())
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    # Mock document with two pictures: first fails, second succeeds
    mock_doc = MagicMock(spec=DoclingDocument)

    mock_picture1 = MagicMock()
    mock_picture1.image.pil_image.save.side_effect = Exception("First failed")

    mock_picture2 = MagicMock()
    # mock_picture2.image.pil_image.save should succeed by default

    mock_doc.pictures = [mock_picture1, mock_picture2]

    # Act
    with caplog.at_level(logging.WARNING):
        converter._save_images(mock_doc, images_dir)

    # Assert
    assert "Failed to save image" in caplog.text
    assert "First failed" in caplog.text

    # Verify both were attempted
    assert mock_picture1.image.pil_image.save.call_count == 1
    assert mock_picture2.image.pil_image.save.call_count == 1

    # Verify the second one was called with the correct path
    expected_path2 = images_dir / "picture_2.png"
    mock_picture2.image.pil_image.save.assert_called_with(expected_path2)
