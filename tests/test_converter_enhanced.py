import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from docling_lib.converter import DocumentConversionOptions, PDFConverter, EnhancedMarkdownSerializer
from docling_core.types.doc import DoclingDocument
from docling.datamodel.pipeline_options import PdfPipelineOptions

def test_enhanced_markdown_serializer_initialization_real_doc():
    """Test that EnhancedMarkdownSerializer initializes correctly with a real DoclingDocument."""
    doc = DoclingDocument(name="test")
    serializer = EnhancedMarkdownSerializer(doc=doc)
    assert serializer.doc == doc
    assert serializer._custom_table_format == "html"
    assert hasattr(serializer, "table_serializer")

def test_pdf_converter_options_propagation():
    """Test that conversion options are correctly propagated to PdfPipelineOptions."""
    options = DocumentConversionOptions(
        image_scale=3.0,
        do_formula=False,
        do_ocr=False,
        do_chart=True,
        do_code=True
    )
    
    with patch("docling_lib.converter.DocumentConverter") as mock_converter_cls:
        converter = PDFConverter(options=options)
        
        # Verify PdfPipelineOptions configuration
        # In PDFConverter.__init__, PdfFormatOption is called with pipeline_options
        args, kwargs = mock_converter_cls.call_args
        format_options = kwargs.get("format_options")
        
        # Extract the InputFormat.PDF option (we know it's there from code)
        from docling.datamodel.base_models import InputFormat
        pdf_options = format_options[InputFormat.PDF]
        pipeline_opts = pdf_options.pipeline_options
        
        assert pipeline_opts.images_scale == 3.0
        assert pipeline_opts.do_formula_enrichment is False
        assert pipeline_opts.do_ocr is False
        assert pipeline_opts.do_chart_extraction is True
        assert pipeline_opts.do_code_enrichment is True

def test_pdf_converter_save_markdown_security_resolution(tmp_path):
    """Test security checks in _save_markdown against path traversal."""
    converter = PDFConverter()
    doc = DoclingDocument(name="test")
    
    # Valid case
    output_dir = tmp_path / "safe"
    output_dir.mkdir()
    res_path = converter._save_markdown(doc, output_dir)
    assert res_path.exists()
    assert res_path.is_relative_to(output_dir)

    # Malicious image_dir_name
    malicious_options = DocumentConversionOptions(image_dir_name="../evil")
    with pytest.raises(ValueError, match="Traversal detected in image directory"):
        converter._save_markdown(doc, output_dir, options=malicious_options)

    # Malicious md_output_name
    malicious_options_2 = DocumentConversionOptions(md_output_name="/etc/passwd")
    with pytest.raises(ValueError, match="Traversal detected in markdown output name"):
        converter._save_markdown(doc, output_dir, options=malicious_options_2)
