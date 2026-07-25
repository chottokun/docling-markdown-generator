import logging
from unittest.mock import MagicMock, patch

import pytest
from docling_core.types.doc import DoclingDocument

from docling_lib.converter import PDFConverter


@pytest.fixture
def converter():
    # Patch DocumentConverter to avoid real initialization if possible,
    # though PDFConverter.__init__ already called it if we didn't mock it before import.
    with patch("docling_lib.converter.DocumentConverter") as mock_conv_cls:
        mock_conv = mock_conv_cls.return_value
        conv = PDFConverter()
        conv.doc_converter = mock_conv
        return conv


def test_os_error_propagation(converter, tmp_path):
    """Verify that OSError from doc_converter.convert is propagated."""
    input_path = tmp_path / "test.pdf"
    input_path.touch()
    output_dir = tmp_path / "output"

    converter.doc_converter.convert.side_effect = OSError("Simulated OS Error")

    with pytest.raises(OSError) as excinfo:
        converter.convert(input_path, output_dir)
    assert "Simulated OS Error" in str(excinfo.value)


def test_permission_error_propagation(converter, tmp_path):
    """Verify that PermissionError from doc_converter.convert is propagated."""
    input_path = tmp_path / "test.pdf"
    input_path.touch()
    output_dir = tmp_path / "output"

    converter.doc_converter.convert.side_effect = PermissionError(
        "Simulated Permission Error"
    )

    with pytest.raises(PermissionError) as excinfo:
        converter.convert(input_path, output_dir)
    assert "Simulated Permission Error" in str(excinfo.value)


def test_generic_exception_handling(converter, tmp_path, caplog):
    """Verify that generic Exception from doc_converter.convert is caught and logged."""
    input_path = tmp_path / "test.pdf"
    input_path.touch()
    output_dir = tmp_path / "output"

    converter.doc_converter.convert.side_effect = ValueError("Simulated Generic Error")

    with caplog.at_level(logging.ERROR):
        result = converter.convert(input_path, output_dir)

    assert result is None
    assert "Error converting document" in caplog.text
    assert "Simulated Generic Error" in caplog.text


def test_os_error_propagation_from_save_markdown(converter, tmp_path):
    """Verify that OSError raised during downstream saving of markdown is propagated."""
    input_path = tmp_path / "test.pdf"
    input_path.touch()
    output_dir = tmp_path / "output"

    # Mock the direct convert to return a document
    mock_doc = MagicMock(spec=DoclingDocument)
    mock_doc.name = "Test Document"
    mock_doc.pictures = []
    converter.doc_converter.convert.return_value.document = mock_doc

    # Mock _save_markdown to raise OSError
    with patch.object(converter, "_save_markdown", side_effect=OSError("Downstream OS Error")):
        with pytest.raises(OSError) as excinfo:
            converter.convert(input_path, output_dir)
        assert "Downstream OS Error" in str(excinfo.value)


def test_permission_error_propagation_from_save_markdown(converter, tmp_path):
    """Verify that PermissionError raised during downstream saving of markdown is propagated."""
    input_path = tmp_path / "test.pdf"
    input_path.touch()
    output_dir = tmp_path / "output"

    # Mock the direct convert to return a document
    mock_doc = MagicMock(spec=DoclingDocument)
    mock_doc.name = "Test Document"
    mock_doc.pictures = []
    converter.doc_converter.convert.return_value.document = mock_doc

    # Mock _save_markdown to raise PermissionError
    with patch.object(converter, "_save_markdown", side_effect=PermissionError("Downstream Permission Error")):
        with pytest.raises(PermissionError) as excinfo:
            converter.convert(input_path, output_dir)
        assert "Downstream Permission Error" in str(excinfo.value)
