import docling_lib
from docling_lib.converter import PDFConverter, DocumentConversionOptions, process_pdf

def test_exports():
    """Verify that the expected members are exported from the package."""
    assert hasattr(docling_lib, "PDFConverter")
    assert hasattr(docling_lib, "DocumentConversionOptions")
    assert hasattr(docling_lib, "process_pdf")

def test_export_identities():
    """Verify that exported members are the correct objects from the converter module."""
    assert docling_lib.PDFConverter is PDFConverter
    assert docling_lib.DocumentConversionOptions is DocumentConversionOptions
    assert docling_lib.process_pdf is process_pdf

def test_all_contains_exports():
    """Verify that __all__ contains the expected exports."""
    assert "PDFConverter" in docling_lib.__all__
    assert "DocumentConversionOptions" in docling_lib.__all__
    assert "process_pdf" in docling_lib.__all__
