import pytest
from fastapi import HTTPException
import docling_lib.server
from docling_lib.server import _validate_extension, _create_output_dir, _validate_content_length
from docling_lib.config import MAX_UPLOAD_SIZE

@pytest.mark.parametrize("content_length", [
    None,
    0,
    1024,
    MAX_UPLOAD_SIZE,
])
def test_validate_content_length_valid(content_length):
    # Should not raise any exception
    _validate_content_length(content_length)

@pytest.mark.parametrize("content_length", [
    MAX_UPLOAD_SIZE + 1,
    MAX_UPLOAD_SIZE + 1024,
])
def test_validate_content_length_invalid(content_length):
    with pytest.raises(HTTPException) as exc_info:
        _validate_content_length(content_length)
    assert exc_info.value.status_code == 413
    assert "Payload Too Large" in exc_info.value.detail

@pytest.mark.parametrize("filename, expected_ext", [
    ("test.pdf", ".pdf"),
    ("document.docx", ".docx"),
    ("presentation.pptx", ".pptx"),
    ("spreadsheet.xlsx", ".xlsx"),
    ("TEST.PDF", ".pdf"),
    ("Document.Docx", ".docx"),
    ("multi.dot.file.pdf", ".pdf"),
    ("path/to/file.xlsx", ".xlsx"),
])
def test_validate_extension_valid(filename, expected_ext):
    assert _validate_extension(filename) == expected_ext

@pytest.mark.parametrize("filename", [
    ("test.txt"),
    ("image.png"),
    ("archive.zip"),
    ("README"),
    ("no_extension."),
    (".pdf"), # This is tricky, Path(".pdf").suffix is ""
    ("file."),
])
def test_validate_extension_invalid(filename):
    with pytest.raises(HTTPException) as exc_info:
        _validate_extension(filename)
    assert exc_info.value.status_code == 400
    assert "Unsupported file format" in exc_info.value.detail

@pytest.mark.asyncio
async def test_create_output_dir(tmp_path, monkeypatch):
    """Test that _create_output_dir creates a unique directory and returns its ID and path."""
    # Setup: Redirect OUTPUT_DIR to a temporary directory
    monkeypatch.setattr(docling_lib.server, "OUTPUT_DIR", tmp_path)

    # Act
    request_id, request_output_dir = await _create_output_dir()

    # Assert
    assert isinstance(request_id, str)
    assert len(request_id) == 16  # 8 bytes hex
    assert request_output_dir == tmp_path / request_id
    assert request_output_dir.exists()
    assert request_output_dir.is_dir()
