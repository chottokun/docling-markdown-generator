import os
import pytest
from pathlib import Path
from docling_lib.converter import process_pdf

REAL_WORLD_DATA_DIR = Path(__file__).parent / "data" / "real_world"

@pytest.fixture
def clean_output_dir(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

@pytest.mark.parametrize("pdf_file", [
    f for f in REAL_WORLD_DATA_DIR.iterdir() if f.is_file() and f.suffix.lower() in [".pdf", ".docx", ".pptx", ".xlsx"]
] if REAL_WORLD_DATA_DIR.exists() else [])
def test_real_world_pdf_conversion(pdf_file, clean_output_dir, monkeypatch):
    """
    Test the converter using various real-world PDFs downloaded from the web.
    Checks that the markdown string is generated and no exceptions are thrown.
    """
    monkeypatch.chdir(clean_output_dir)
    # Create isolated output directory for each test
    file_output_dir = clean_output_dir / pdf_file.stem
    file_output_dir.mkdir(exist_ok=True)
    
    # Process the PDF
    try:
        markdown_output = process_pdf(pdf_file, file_output_dir)
    except Exception as e:
        pytest.fail(f"Conversion failed for {pdf_file.name} with exception: {e}")

    # Assert basic output validity
    assert markdown_output is not None, f"Conversion returned None for {pdf_file.name}"
    assert isinstance(markdown_output, Path), f"Output is not a Path for {pdf_file.name}"
    assert markdown_output.exists(), f"Output file does not exist for {pdf_file.name}"
    
    # Also verify that a markdown file might be saved internally by Docling,
    # though process_pdf returns the text directly. 
    # Optional: We could check if images are extracted in file_output_dir
