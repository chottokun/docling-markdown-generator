import docling_lib


def test_init_exports():
    """Verify that docling_lib correctly exports the primary API."""
    assert hasattr(docling_lib, "PDFConverter")
    assert hasattr(docling_lib, "DocumentConversionOptions")
    assert hasattr(docling_lib, "process_pdf")


def test_init_version():
    """Verify that docling_lib has the correct version."""
    assert hasattr(docling_lib, "__version__")
    assert docling_lib.__version__ == "0.1.0"


def test_all_export_consistency():
    """Verify that __all__ matches the exported members."""
    expected_exports = ["PDFConverter", "DocumentConversionOptions", "process_pdf"]
    assert sorted(docling_lib.__all__) == sorted(expected_exports)
