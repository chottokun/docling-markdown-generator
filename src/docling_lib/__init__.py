"""docling_lib package."""

try:
    from .converter import (
        DocumentConversionOptions,
        EnhancedDoclingConverter,
        PDFConverter,
        process_pdf,
    )
except ImportError:
    # Fallback when docling is not installed (e.g., lightweight lint/test CI runs)
    pass

__version__ = "0.1.0"
__all__ = [
    "PDFConverter",
    "DocumentConversionOptions",
    "process_pdf",
    "EnhancedDoclingConverter",
]
