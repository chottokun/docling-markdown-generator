from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from docling_core.types.doc import FormulaItem, ImageRefMode

from docling_lib.converter import EnhancedMarkdownTextSerializer, PDFConverter
from docling_lib.cli import setup_parser
from docling_lib.server import app


def test_enhanced_markdown_text_serializer_inline():
    """Test that EnhancedMarkdownTextSerializer formats inline math with custom delimiters."""
    serializer = EnhancedMarkdownTextSerializer(
        math_inline_delim="\\(",
        math_block_delim="\\[",
        math_block_newline=False,
    )
    item = FormulaItem(self_ref="#/formula/1", text="x + y = z", orig="x + y = z")
    doc_serializer = MagicMock()
    doc_serializer.post_process = lambda text, **kwargs: text
    doc = MagicMock()

    # Test as inline
    res_inline = serializer.serialize(
        item=item,
        doc_serializer=doc_serializer,
        doc=doc,
        is_inline_scope=True,
    )
    assert res_inline.text == "\\(x + y = z\\)"


def test_enhanced_markdown_text_serializer_block():
    """Test that EnhancedMarkdownTextSerializer formats block math with/without newlines."""
    # Without block newline
    serializer_no_nl = EnhancedMarkdownTextSerializer(
        math_inline_delim="$",
        math_block_delim="$$",
        math_block_newline=False,
    )
    item = FormulaItem(self_ref="#/formula/1", text="x + y = z", orig="x + y = z")
    doc_serializer = MagicMock()
    doc_serializer.post_process = lambda text, **kwargs: text
    doc = MagicMock()

    res_no_nl = serializer_no_nl.serialize(
        item=item,
        doc_serializer=doc_serializer,
        doc=doc,
        is_inline_scope=False,
    )
    assert res_no_nl.text == "$$x + y = z$$"

    # With block newline
    serializer_nl = EnhancedMarkdownTextSerializer(
        math_inline_delim="$",
        math_block_delim="$$",
        math_block_newline=True,
    )
    res_nl = serializer_nl.serialize(
        item=item,
        doc_serializer=doc_serializer,
        doc=doc,
        is_inline_scope=False,
    )
    assert res_nl.text == "$$\nx + y = z\n$$"


def test_auto_math_delimiters():
    """Test that math delimiters are automatically detected based on the document type (e.g. .tex vs others)."""
    serializer = EnhancedMarkdownTextSerializer(
        math_inline_delim="auto",
        math_block_delim="auto",
    )
    item = FormulaItem(self_ref="#/formula/1", text="a + b = c", orig="a + b = c")
    doc_serializer = MagicMock()
    doc_serializer.post_process = lambda text, **kwargs: text

    # Standard document (PDF/HTML/etc) -> should use $ and $$
    doc_pdf = MagicMock()
    doc_pdf.name = "math_paper.pdf"

    res_inline_pdf = serializer.serialize(
        item=item, doc_serializer=doc_serializer, doc=doc_pdf, is_inline_scope=True
    )
    assert res_inline_pdf.text == "$a + b = c$"

    res_block_pdf = serializer.serialize(
        item=item, doc_serializer=doc_serializer, doc=doc_pdf, is_inline_scope=False
    )
    assert res_block_pdf.text == "$$a + b = c$$"

    # LaTeX document (.tex / .latex) -> should use \( and \[
    doc_tex = MagicMock()
    doc_tex.name = "quantum_mechanics.tex"

    res_inline_tex = serializer.serialize(
        item=item, doc_serializer=doc_serializer, doc=doc_tex, is_inline_scope=True
    )
    assert res_inline_tex.text == "\\(a + b = c\\)"

    res_block_tex = serializer.serialize(
        item=item, doc_serializer=doc_serializer, doc=doc_tex, is_inline_scope=False
    )
    assert res_block_tex.text == "\\[a + b = c\\]"


def test_auto_block_newline_complexity():
    """Test that block newline formatting is automatically determined based on formula complexity."""
    serializer = EnhancedMarkdownTextSerializer(
        math_inline_delim="$",
        math_block_delim="$$",
        math_block_newline="auto",
    )
    doc_serializer = MagicMock()
    doc_serializer.post_process = lambda text, **kwargs: text
    doc = MagicMock()

    # Simple formula -> single-line (saves tokens/layout space)
    simple_item = FormulaItem(self_ref="#/formula/1", text="E = mc^2", orig="E = mc^2")
    res_simple = serializer.serialize(
        item=simple_item, doc_serializer=doc_serializer, doc=doc, is_inline_scope=False
    )
    assert res_simple.text == "$$E = mc^2$$"

    # Complex formula (long length > 60 chars) -> multi-line
    long_text = "x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a} + \\int_{a}^{b} f(t) dt + g(x)"
    complex_item_long = FormulaItem(self_ref="#/formula/2", text=long_text, orig=long_text)
    res_complex_long = serializer.serialize(
        item=complex_item_long, doc_serializer=doc_serializer, doc=doc, is_inline_scope=False
    )
    assert res_complex_long.text == f"$$\n{long_text}\n$$"

    # Complex formula (contains multiline LaTeX commands like \\ or \begin) -> multi-line
    multiline_text = "A = \\begin{pmatrix} 1 & 0 \\\\ 0 & 1 \\end{pmatrix}"
    complex_item_multiline = FormulaItem(self_ref="#/formula/3", text=multiline_text, orig=multiline_text)
    res_complex_multiline = serializer.serialize(
        item=complex_item_multiline, doc_serializer=doc_serializer, doc=doc, is_inline_scope=False
    )
    assert res_complex_multiline.text == f"$$\n{multiline_text}\n$$"


def test_pdf_converter_math_options_propagation():
    """Test that PDFConverter propagates math formatting options down to the serializer."""
    converter = PDFConverter()
    mock_doc = MagicMock()
    table_format = "html"

    with (
        patch(
            "docling_lib.converter.EnhancedMarkdownSerializer"
        ) as mock_serializer_cls,
        patch("docling_lib.converter.MarkdownParams") as mock_params_cls,
    ):
        mock_serializer_inst = mock_serializer_cls.return_value
        mock_ser_res = MagicMock()
        mock_ser_res.text = "Mock Content"
        mock_serializer_inst.serialize.return_value = mock_ser_res

        # Call with custom options
        from docling_lib.converter import DocumentConversionOptions
        custom_options = DocumentConversionOptions(
            math_inline_delim="\\(",
            math_block_delim="\\[",
            math_block_newline=True,
        )

        converter._serialize_to_markdown(
            mock_doc, table_format, options=custom_options
        )

        # Assert custom math parameters were passed to EnhancedMarkdownSerializer
        mock_serializer_cls.assert_called_once_with(
            doc=mock_doc,
            table_format=table_format,
            vlm_enabled=False,
            vlm_provider="ollama",
            vlm_api_key="",
            vlm_model="qwen2-vl:2b",
            vlm_endpoint="http://localhost:11434",
            vlm_prompt=(
                "この画像の概要を1〜2文程度で簡潔に日本語で説明してください。"
                "なお、グラフや図表の場合は主要な数値や傾向（増減・ピークなど）を含めて説明してください。"
            ),
            vlm_max_concurrent=5,
            vlm_captions={},
            image_dir_name="images",
            image_tag_template=None,
            slug=None,
            math_inline_delim="\\(",
            math_block_delim="\\[",
            math_block_newline=True,
            params=mock_params_cls.return_value,
        )


def test_cli_math_arguments():
    """Test that the CLI parser successfully parses math delimiter options."""
    parser = setup_parser()
    args = parser.parse_args([
        "dummy.pdf",
        "--math-inline-delim", "\\(",
        "--math-block-delim", "\\[",
        "--math-block-newline", "true",
    ])
    assert args.math_inline_delim == "\\("
    assert args.math_block_delim == "\\["
    assert args.math_block_newline == "true"


def test_fastapi_server_math_form_fields():
    """Test that the FastAPI server dependency extracts and validates math form fields."""
    client = TestClient(app)
    # We mock process_pdf to avoid doing actual file conversions
    with patch("docling_lib.server.process_pdf") as mock_process_pdf:
        mock_process_pdf.return_value = None

        # Call the convert endpoint with math parameters
        response = client.post(
            "/convert/",
            headers={"x-api-key": "test_api_key"},  # The global_api_key_override fixture handles this
            files={"file": ("dummy.pdf", b"pdfcontent", "application/pdf")},
            data={
                "math_inline_delim": "\\(",
                "math_block_delim": "\\[",
                "math_block_newline": "True",
            },
        )
        # It might return a 500 or 404 because file processing returned None, but we want to inspect
        # the options parsed by the endpoint.
        assert mock_process_pdf.called
        called_args = mock_process_pdf.call_args
        # options is a kwarg
        options = called_args[1].get("options")
        assert options is not None
        assert options.math_inline_delim == "\\("
        assert options.math_block_delim == "\\["
        assert options.math_block_newline is True
