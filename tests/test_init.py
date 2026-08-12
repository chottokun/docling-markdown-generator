import docling_lib
from docling_lib.converter import DocumentConversionOptions, PDFConverter, process_pdf


def test_exports():
    """Verify that docling_lib correctly exports the primary API."""
    assert hasattr(docling_lib, "PDFConverter")
    assert hasattr(docling_lib, "DocumentConversionOptions")
    assert hasattr(docling_lib, "process_pdf")


def test_export_identities():
    """Verify that exported members are the correct objects from the converter module."""
    assert docling_lib.PDFConverter is PDFConverter
    assert docling_lib.DocumentConversionOptions is DocumentConversionOptions
    assert docling_lib.process_pdf is process_pdf


def test_init_version():
    """Verify that docling_lib has the correct version."""
    assert hasattr(docling_lib, "__version__")
    assert docling_lib.__version__ == "0.1.0"


def test_all_export_consistency():
    """Verify that __all__ matches the exported members."""
    expected_exports = [
        "PDFConverter",
        "DocumentConversionOptions",
        "process_pdf",
        "EnhancedDoclingConverter",
    ]
    assert sorted(docling_lib.__all__) == sorted(expected_exports)
