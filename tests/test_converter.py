import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from docling.datamodel.base_models import InputFormat
from docling_core.types.doc import DoclingDocument

from docling_lib.converter import process_pdf

# --- Fixtures ---

@pytest.fixture(autouse=True)
def reset_shared_converter():
    """Resets the shared default converter before and after each test."""
    import docling_lib.converter as converter_mod
    converter_mod._default_pdf_converter = None
    yield
    converter_mod._default_pdf_converter = None

@pytest.fixture
def pdf_downloader(tmp_path):
    """Fixture to provide a path to a real PDF, downloading if necessary."""
    def _downloader(url):
        filename = url.split("/")[-1]
        test_data_dir = Path(__file__).parent / "test_data"
        test_data_dir.mkdir(exist_ok=True)
        local_path = test_data_dir / filename
        if not local_path.exists():
            import requests
            response = requests.get(url, timeout=30)
            local_path.write_bytes(response.content)
        return local_path
    return _downloader

# --- Test Cases ---

@patch("docling_lib.converter.DocumentConverter")
@patch("docling_lib.converter.EnhancedMarkdownSerializer")
def test_process_pdf_calls_docling_api_correctly(
    MockSerializer, MockDocumentConverter, tmp_path, pdf_downloader, monkeypatch
):
    """
    Verify that process_pdf initializes the converter and serializer with correct options.
    """
    monkeypatch.chdir(tmp_path)
    pdf_path = pdf_downloader("https://arxiv.org/pdf/2406.12430.pdf")
    
    # Setup mocks
    mock_doc = MagicMock(spec=DoclingDocument)
    mock_doc.name = "Test Document"
    MockDocumentConverter.return_value.convert.return_value.document = mock_doc
    
    mock_serializer_instance = MockSerializer.return_value
    mock_serializer_instance.serialize.return_value.text = "# Mocked Markdown"

    output_dir = tmp_path
    expected_md_path = output_dir / "processed_document.md"

    # Act
    result_path = process_pdf(pdf_path, output_dir)

    # Assert
    # Verify converter options
    _, init_kwargs = MockDocumentConverter.call_args
    pipeline_opts = init_kwargs["format_options"][InputFormat.PDF].pipeline_options
    assert pipeline_opts.generate_picture_images is True
    assert pipeline_opts.images_scale == 2.0
    assert pipeline_opts.do_formula_enrichment is True

    # Verify serializer was initialized
    MockSerializer.assert_called_once()
    assert result_path == expected_md_path
    assert expected_md_path.exists()


def test_process_pdf_e2e_happy_path(tmp_path, pdf_downloader, monkeypatch):
    """
    End-to-end test with a real PDF.
    """
    monkeypatch.chdir(tmp_path)
    pdf_path = pdf_downloader("https://arxiv.org/pdf/2406.12430.pdf")
    output_dir = tmp_path / "output"
    
    # This will actually run Docling
    result_path = process_pdf(pdf_path, output_dir)

    assert result_path is not None
    assert result_path.exists()
    content = result_path.read_text(encoding="utf-8")
    assert len(content) > 100
    assert "---" in content  # Metadata frontmatter


def test_process_docx_e2e_happy_path(tmp_path, monkeypatch):
    """
    End-to-end test with a real DOCX.
    """
    monkeypatch.chdir(tmp_path)
    src_docx = Path(__file__).parent / "test_data" / "word_sample.docx"
    if not src_docx.exists():
        pytest.skip("word_sample.docx not found")
    
    import shutil
    shutil.copy(src_docx, tmp_path / "sample.docx")
    
    output_dir = tmp_path / "output"
    result_path = process_pdf(tmp_path / "sample.docx", output_dir)

    assert result_path is not None
    assert result_path.exists()
    images_dir = output_dir / "images"
    assert images_dir.exists()


@patch("docling_lib.converter.DocumentConverter")
def test_process_pdf_with_explicit_converter(
    MockDocumentConverter, tmp_path, pdf_downloader, monkeypatch
):
    """
    Verify that process_pdf uses the provided converter instance.
    """
    monkeypatch.chdir(tmp_path)
    pdf_path = pdf_downloader("https://arxiv.org/pdf/2406.12430.pdf")
    
    mock_explicit_converter = MagicMock()
    mock_doc = MagicMock(spec=DoclingDocument)
    mock_doc.name = "Explicit Doc"
    mock_explicit_converter.convert.return_value.document = mock_doc
    
    # We need to mock EnhancedMarkdownSerializer to avoid Pydantic issues with the mock_doc
    with patch("docling_lib.converter.EnhancedMarkdownSerializer") as MockSerializer:
        MockSerializer.return_value.serialize.return_value.text = "Explicit Content"
        
        result = process_pdf(pdf_path, tmp_path, converter=mock_explicit_converter)
    
    assert result is not None
    mock_explicit_converter.convert.assert_called_once_with(pdf_path)
    # The DocumentConverter (Docling's own) is instantiated once by our shared wrapper.
    assert MockDocumentConverter.call_count == 1


@patch("docling_lib.converter.EnhancedMarkdownSerializer")
@patch("docling_lib.converter.DocumentConverter")
def test_process_pdf_unexpected_workflow_error(
    MockDocumentConverter, MockSerializer, tmp_path, caplog, monkeypatch
):
    """
    Verify handling of unexpected exceptions.
    """
    monkeypatch.chdir(tmp_path)
    pdf_path = tmp_path / "test.pdf"
    pdf_path.touch()

    MockSerializer.return_value.serialize.side_effect = Exception("Crash")

    with caplog.at_level(logging.ERROR):
        result = process_pdf(pdf_path, tmp_path)

    assert result is None
    assert any("Workflow Error" in record.message or "Error converting document" in record.message 
               for record in caplog.records)


def test_process_pdf_path_traversal_prevention(tmp_path, pdf_downloader, monkeypatch):
    """
    Verify path traversal protection.
    """
    monkeypatch.chdir(tmp_path)
    pdf_path = pdf_downloader("https://arxiv.org/pdf/2406.12430.pdf")
    malicious_dir = tmp_path / "../outside"
    
    result = process_pdf(pdf_path, malicious_dir)
    assert result is None
