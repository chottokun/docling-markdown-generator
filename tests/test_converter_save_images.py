import logging
from unittest.mock import MagicMock, patch

from docling_core.types.doc import DoclingDocument

from docling_lib.converter import DocumentConversionOptions, PDFConverter


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


def test_save_markdown_image_save_failure(tmp_path, caplog):
    """
    Verify that when save_markdown_with_images (which executes _save_markdown) encounters
    an exception during image saving, the entire saving flow completes successfully, does not
    propagate/raise the error, and correctly logs the warning message.
    """
    # Setup
    converter = PDFConverter(options=DocumentConversionOptions())
    output_dir = tmp_path / "output"

    # Mock document
    mock_doc = MagicMock(spec=DoclingDocument)
    mock_doc.name = "Test Document"

    # Add a mock image that fails to save
    mock_picture = MagicMock()
    mock_picture.image.pil_image.save.side_effect = Exception("Markdown flow image save failure")
    mock_doc.pictures = [mock_picture]

    # Mock EnhancedMarkdownSerializer to avoid complex serialization logic and Pydantic issues
    with patch("docling_lib.converter.EnhancedMarkdownSerializer") as MockSerializer:
        mock_serializer_instance = MockSerializer.return_value
        mock_serializer_instance.serialize.return_value.text = "# Mock Document Content"

        with caplog.at_level(logging.WARNING):
            res_path = converter._save_markdown(mock_doc, output_dir)

    # Assert that the output file is still written successfully
    expected_md_path = output_dir / "processed_document.md"
    assert res_path == expected_md_path
    assert expected_md_path.exists()
    assert expected_md_path.read_text(encoding="utf-8") == "---\ntitle: Test Document\n---\n\n# Mock Document Content"

    # Assert that the image save warning was logged
    assert "Failed to save image" in caplog.text
    assert "Markdown flow image save failure" in caplog.text

    # Assert the image save was indeed attempted
    mock_picture.image.pil_image.save.assert_called_once()
