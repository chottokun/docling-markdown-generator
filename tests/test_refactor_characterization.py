import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.docling_lib.config import DOCLING_ARTIFACTS_PATH
from src.docling_lib.converter import DocumentConversionOptions, PDFConverter
from src.docling_lib.utils import (
    extract_excel_images,
    generate_doc_slug,
    generate_image_filename,
    get_picture_page_no,
)


def test_characterization_extract_excel_images_invalid_inputs():
    """Verify extract_excel_images handling of invalid files or non-zip bytes."""
    assert extract_excel_images(b"invalid_bytes_content") == []
    assert extract_excel_images(Path("non_existent_file_path.xlsx")) == []


def test_characterization_extract_excel_images_empty_zip():
    """Verify extract_excel_images handling of zip archives lacking OpenXML structure."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dummy.txt", "content")
    assert extract_excel_images(buf.getvalue()) == []


def test_characterization_slug_and_filename_generation():
    """Verify boundary cases for slug and image filename generation."""
    assert generate_doc_slug(None) == "document"
    assert generate_doc_slug("") == "document"
    assert generate_doc_slug("  ") == "document"
    assert generate_doc_slug("My/Doc:Name*.pdf") == "Doc-Name"
    assert generate_doc_slug("Doc Name.pdf") == "Doc-Name"

    assert generate_image_filename("slug", 1, 1) == "slug_p1_1.png"
    # Negative/zero values bounded to 1
    assert generate_image_filename("slug", -5, 0) == "slug_p1_1.png"


def test_characterization_get_picture_page_no():
    """Verify page number extraction from picture item provenance."""
    pic = MagicMock()
    pic.prov = []
    assert get_picture_page_no(pic) == 1

    prov_item = MagicMock()
    prov_item.page_no = 3
    pic.prov = [prov_item]
    assert get_picture_page_no(pic) == 3


def test_characterization_pdf_converter_format_options():
    """Verify PDFConverter initializes format options properly."""
    options = DocumentConversionOptions()
    converter = PDFConverter(options)
    assert converter.options.image_dir_name == "images"
    assert converter.doc_converter is not None


def test_characterization_config_artifacts_path():
    """Verify DOCLING_ARTIFACTS_PATH configuration exists and is properly typed."""
    assert DOCLING_ARTIFACTS_PATH is None or isinstance(DOCLING_ARTIFACTS_PATH, Path)
