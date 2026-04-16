import pytest
from fastapi import HTTPException
from docling_lib.server import _validate_extension

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
