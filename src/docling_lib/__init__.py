"""docling_lib package."""

try:
    from .converter import (
        DocumentConversionOptions as DocumentConversionOptions,
    )
    from .converter import (
        EnhancedDoclingConverter as EnhancedDoclingConverter,
    )
    from .converter import (
        PDFConverter as PDFConverter,
    )
    from .converter import (
        process_pdf as process_pdf,
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
