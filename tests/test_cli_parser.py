from pathlib import Path

import pytest

from tests.mock_docling import mock_docling

# Call mock_docling before importing cli to handle missing dependencies
mock_docling()

from docling_lib.cli import _resolve_api_key, setup_parser
from docling_lib.config import (
    DO_CHART,
    DO_CODE,
    DO_FORMULA,
    DO_OCR,
    DOCLING_CUDA_FLASH_ATTENTION,
    DOCLING_INCLUDE_KV_EXTRACTION,
    DOCLING_INCLUDE_PAGE_BREAKS,
    DOCLING_NUM_THREADS,
    DOCLING_TABLE_FORMAT,
    DOCLING_VLM_ENABLED,
    DOCLING_VLM_ENDPOINT,
    DOCLING_VLM_MAX_CONCURRENT,
    DOCLING_VLM_MODEL,
    DOCLING_VLM_PROMPT,
    DOCLING_VLM_PROVIDER,
    IMAGE_DIR_NAME,
    IMAGE_RESOLUTION_SCALE,
    MD_OUTPUT_NAME,
)


def test_setup_parser_defaults():
    """Test that setup_parser returns a parser with expected default values."""
    parser = setup_parser()
    args = parser.parse_args(["test.pdf"])

    assert args.pdf_file == Path("test.pdf")
    assert args.output_dir == Path("output")
    assert args.image_dir == IMAGE_DIR_NAME
    assert args.output_name == MD_OUTPUT_NAME
    assert args.image_scale == IMAGE_RESOLUTION_SCALE
    assert args.table_format == DOCLING_TABLE_FORMAT
    assert args.include_page_breaks == DOCLING_INCLUDE_PAGE_BREAKS
    assert args.include_kv_extraction == DOCLING_INCLUDE_KV_EXTRACTION
    assert args.vlm_enabled == DOCLING_VLM_ENABLED
    assert args.vlm_provider == DOCLING_VLM_PROVIDER
    assert args.vlm_model == DOCLING_VLM_MODEL
    assert args.vlm_endpoint == DOCLING_VLM_ENDPOINT
    assert args.vlm_prompt == DOCLING_VLM_PROMPT
    assert args.vlm_max_concurrent == DOCLING_VLM_MAX_CONCURRENT
    assert args.do_ocr == DO_OCR
    assert args.do_formula == DO_FORMULA
    assert args.do_chart == DO_CHART
    assert args.do_code == DO_CODE
    assert args.num_threads == DOCLING_NUM_THREADS
    assert args.cuda_use_flash_attention == DOCLING_CUDA_FLASH_ATTENTION


def test_setup_parser_boolean_optional_actions():
    """Test positive and negative toggles using argparse.BooleanOptionalAction."""
    parser = setup_parser()

    # Test disabling OCR & formula, enabling VLM & page breaks & chart
    args = parser.parse_args(
        [
            "test.pdf",
            "--no-ocr",
            "--no-formula",
            "--vlm",
            "--include-page-breaks",
            "--chart",
            "--code",
            "--cuda-flash-attention",
        ]
    )

    assert args.do_ocr is False
    assert args.do_formula is False
    assert args.vlm_enabled is True
    assert args.include_page_breaks is True
    assert args.do_chart is True
    assert args.do_code is True
    assert args.cuda_use_flash_attention is True

    # Test vice versa
    args2 = parser.parse_args(
        [
            "test.pdf",
            "--ocr",
            "--formula",
            "--no-vlm",
            "--no-include-page-breaks",
            "--no-chart",
            "--no-code",
            "--no-cuda-flash-attention",
        ]
    )

    assert args2.do_ocr is True
    assert args2.do_formula is True
    assert args2.vlm_enabled is False
    assert args2.include_page_breaks is False
    assert args2.do_chart is False
    assert args2.do_code is False
    assert args2.cuda_use_flash_attention is False


def test_setup_parser_vlm_and_table_choices():
    """Test choices validation for table-format and vlm-provider."""
    parser = setup_parser()

    args = parser.parse_args(
        [
            "test.pdf",
            "--table-format",
            "markdown",
            "--vlm-provider",
            "openai",
        ]
    )
    assert args.table_format == "markdown"
    assert args.vlm_provider == "openai"

    with pytest.raises(SystemExit):
        parser.parse_args(["test.pdf", "--table-format", "invalid_format"])

    with pytest.raises(SystemExit):
        parser.parse_args(["test.pdf", "--vlm-provider", "invalid_provider"])


def test_resolve_api_key_literal():
    """Test resolving literal API key."""
    assert _resolve_api_key("secret-123") == "secret-123"
    assert _resolve_api_key("") == ""


def test_resolve_api_key_stdin(monkeypatch):
    """Test resolving API key from stdin when '-' is provided."""
    import io
    import sys

    monkeypatch.setattr(sys, "stdin", io.StringIO("stdin-secret-key\n"))
    assert _resolve_api_key("-") == "stdin-secret-key"


def test_resolve_api_key_file(tmp_path):
    """Test resolving API key from secret file when '@path' is provided."""
    key_file = tmp_path / "vlm_key.txt"
    key_file.write_text("file-secret-key\n", encoding="utf-8")

    resolved = _resolve_api_key(f"@{key_file}")
    assert resolved == "file-secret-key"


def test_resolve_api_key_file_missing():
    """Test that missing API key file raises ValueError."""
    with pytest.raises(ValueError, match="Could not read API key file"):
        _resolve_api_key("@non_existent_key_file.txt")
