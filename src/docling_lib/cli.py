import argparse
import logging
import sys
from pathlib import Path

# Import from config and converter
from .config import (
    DO_CHART,
    DO_CODE,
    DO_FORMULA,
    DO_OCR,
    DOCLING_ARTIFACTS_PATH,
    DOCLING_CUDA_FLASH_ATTENTION,
    DOCLING_INCLUDE_KV_EXTRACTION,
    DOCLING_INCLUDE_PAGE_BREAKS,
    DOCLING_MATH_BLOCK_DELIM,
    DOCLING_MATH_BLOCK_NEWLINE,
    DOCLING_MATH_INLINE_DELIM,
    DOCLING_NUM_THREADS,
    DOCLING_TABLE_FORMAT,
    DOCLING_VLM_API_KEY,
    DOCLING_VLM_ENABLED,
    DOCLING_VLM_ENDPOINT,
    DOCLING_VLM_MAX_CONCURRENT,
    DOCLING_VLM_MODEL,
    DOCLING_VLM_PROMPT,
    DOCLING_VLM_PROVIDER,
    IMAGE_DIR_NAME,
    IMAGE_RESOLUTION_SCALE,
    MD_OUTPUT_NAME,
    setup_logging,
)
from .converter import DocumentConversionOptions, process_pdf
from .utils import parse_math_block_newline, sanitize_log_message

# Configure logging for the CLI tool
logger = logging.getLogger(__name__)
setup_logging()


def _resolve_api_key(raw_key: str | None) -> str:
    """
    Resolves VLM API Key string.
    Supports reading from stdin if '-' or from a secret file if '@path'.
    """
    if not raw_key:
        return ""
    if raw_key == "-":
        return sys.stdin.read().strip()
    if raw_key.startswith("@"):
        key_path = Path(raw_key[1:])
        try:
            return key_path.read_text(encoding="utf-8").strip()
        except Exception as e:
            logger.error(
                f"Failed to read API key from file {sanitize_log_message(key_path)}: {sanitize_log_message(e)}"
            )
            raise ValueError(f"Could not read API key file: {key_path}") from e
    return raw_key


def setup_parser():
    """Sets up and returns the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="Extract markdown, figures, and tables from documents (PDF, DOCX, PPTX, XLSX, HTML, XBRL, Email, etc.) with high accuracy."
    )
    parser.add_argument(
        "pdf_file",
        type=Path,
        help="Path to the input document file (PDF, DOCX, PPTX, XLSX, HTML, XBRL, Email, EPUB, LaTeX, WebVTT).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory to save the output files (default: 'output').",
    )
    parser.add_argument(
        "--image-dir",
        type=str,
        default=IMAGE_DIR_NAME,
        help=f"Name of the directory to save extracted images (default: '{IMAGE_DIR_NAME}').",
    )
    parser.add_argument(
        "-n",
        "--output-name",
        type=str,
        default=MD_OUTPUT_NAME,
        help=f"Name of the output Markdown file (default: '{MD_OUTPUT_NAME}').",
    )
    parser.add_argument(
        "-s",
        "--image-scale",
        type=float,
        default=IMAGE_RESOLUTION_SCALE,
        help=f"Image resolution scale (default: {IMAGE_RESOLUTION_SCALE}). Higher values mean better quality but larger files.",
    )

    # Table & RAG control options
    parser.add_argument(
        "--table-format",
        choices=["html", "markdown"],
        default=DOCLING_TABLE_FORMAT,
        help=f"Table serialization format ('html' or 'markdown', default: '{DOCLING_TABLE_FORMAT}').",
    )
    parser.add_argument(
        "--include-page-breaks",
        action=argparse.BooleanOptionalAction,
        default=DOCLING_INCLUDE_PAGE_BREAKS,
        help="Inject page break markers (<!-- PAGE_BREAK: Page N -->) in output.",
    )
    parser.add_argument(
        "--include-kv-extraction",
        action=argparse.BooleanOptionalAction,
        default=DOCLING_INCLUDE_KV_EXTRACTION,
        help="Inject Key Information section for key-value extraction.",
    )

    # VLM options
    parser.add_argument(
        "--vlm",
        dest="vlm_enabled",
        action=argparse.BooleanOptionalAction,
        default=DOCLING_VLM_ENABLED,
        help="Enable VLM image caption generation.",
    )
    parser.add_argument(
        "--vlm-provider",
        choices=["ollama", "openai", "anthropic", "google"],
        default=DOCLING_VLM_PROVIDER,
        help=f"VLM provider name (default: '{DOCLING_VLM_PROVIDER}').",
    )
    parser.add_argument(
        "--vlm-model",
        type=str,
        default=DOCLING_VLM_MODEL,
        help=f"VLM model name (default: '{DOCLING_VLM_MODEL}').",
    )
    parser.add_argument(
        "--vlm-endpoint",
        type=str,
        default=DOCLING_VLM_ENDPOINT,
        help=f"VLM service endpoint URL (default: '{DOCLING_VLM_ENDPOINT}').",
    )
    parser.add_argument(
        "--vlm-api-key",
        type=str,
        default=DOCLING_VLM_API_KEY,
        help="VLM API key (literal string, '-' for stdin, or '@path' to read from secret file).",
    )
    parser.add_argument(
        "--vlm-prompt",
        type=str,
        default=DOCLING_VLM_PROMPT,
        help="Prompt for VLM image caption generation.",
    )
    parser.add_argument(
        "--vlm-max-concurrent",
        type=int,
        default=DOCLING_VLM_MAX_CONCURRENT,
        help=f"Max concurrent VLM API requests (default: {DOCLING_VLM_MAX_CONCURRENT}).",
    )

    # Pipeline control options
    parser.add_argument(
        "--ocr",
        dest="do_ocr",
        action=argparse.BooleanOptionalAction,
        default=DO_OCR,
        help="Enable/disable OCR during conversion.",
    )
    parser.add_argument(
        "--formula",
        dest="do_formula",
        action=argparse.BooleanOptionalAction,
        default=DO_FORMULA,
        help="Enable/disable formula extraction.",
    )
    parser.add_argument(
        "--chart",
        dest="do_chart",
        action=argparse.BooleanOptionalAction,
        default=DO_CHART,
        help="Enable/disable chart extraction.",
    )
    parser.add_argument(
        "--code",
        dest="do_code",
        action=argparse.BooleanOptionalAction,
        default=DO_CODE,
        help="Enable/disable code enrichment.",
    )
    parser.add_argument(
        "--num-threads",
        type=int,
        default=DOCLING_NUM_THREADS,
        help=f"Number of CPU threads for Docling pipeline (default: {DOCLING_NUM_THREADS}).",
    )
    parser.add_argument(
        "--cuda-flash-attention",
        dest="cuda_use_flash_attention",
        action=argparse.BooleanOptionalAction,
        default=DOCLING_CUDA_FLASH_ATTENTION,
        help="Enable/disable CUDA FlashAttention2.",
    )
    parser.add_argument(
        "--artifacts-path",
        type=Path,
        default=DOCLING_ARTIFACTS_PATH,
        help="Path to local Docling model artifacts directory.",
    )

    # Math formatting options
    parser.add_argument(
        "--math-inline-delim",
        type=str,
        default=DOCLING_MATH_INLINE_DELIM,
        help=f"Inline LaTeX math delimiter (default: '{DOCLING_MATH_INLINE_DELIM}').",
    )
    parser.add_argument(
        "--math-block-delim",
        type=str,
        default=DOCLING_MATH_BLOCK_DELIM,
        help=f"Block LaTeX math delimiter (default: '{DOCLING_MATH_BLOCK_DELIM}').",
    )
    parser.add_argument(
        "--math-block-newline",
        type=str,
        default=str(DOCLING_MATH_BLOCK_NEWLINE),
        help="Whether to insert newlines inside LaTeX block math delimiters ('auto', 'true', or 'false').",
    )
    return parser


def main(args=None):
    """
    Main function for the command-line interface.
    Parses arguments and runs the high-accuracy document processing workflow.
    """
    parser = setup_parser()
    parsed_args = parser.parse_args(args if args is not None else sys.argv[1:])

    logger.info(f"Starting high-accuracy workflow for: {parsed_args.pdf_file}")

    math_nl = parse_math_block_newline(parsed_args.math_block_newline)
    resolved_vlm_key = _resolve_api_key(parsed_args.vlm_api_key)

    options = DocumentConversionOptions(
        image_dir_name=parsed_args.image_dir,
        md_output_name=parsed_args.output_name,
        image_scale=parsed_args.image_scale,
        table_format=parsed_args.table_format,
        do_formula=parsed_args.do_formula,
        do_ocr=parsed_args.do_ocr,
        do_chart=parsed_args.do_chart,
        do_code=parsed_args.do_code,
        include_page_breaks=parsed_args.include_page_breaks,
        include_kv_extraction=parsed_args.include_kv_extraction,
        vlm_enabled=parsed_args.vlm_enabled,
        vlm_provider=parsed_args.vlm_provider,
        vlm_api_key=resolved_vlm_key,
        vlm_model=parsed_args.vlm_model,
        vlm_endpoint=parsed_args.vlm_endpoint,
        vlm_prompt=parsed_args.vlm_prompt,
        vlm_max_concurrent=parsed_args.vlm_max_concurrent,
        num_threads=parsed_args.num_threads,
        cuda_use_flash_attention=parsed_args.cuda_use_flash_attention,
        math_inline_delim=parsed_args.math_inline_delim,
        math_block_delim=parsed_args.math_block_delim,
        math_block_newline=math_nl,
        artifacts_path=parsed_args.artifacts_path,
        allow_absolute_output_dir=True,
    )

    # Call the new, unified processing function
    result_path = process_pdf(
        parsed_args.pdf_file,
        parsed_args.output_dir,
        options=options,
    )

    if result_path:
        logger.info(
            f"Workflow completed successfully! Output saved in {parsed_args.output_dir}"
        )
        return 0
    else:
        logger.error("Workflow failed. Please check the logs for details.")
        return 1


def entry_point():
    """Encapsulates the CLI entry point logic for testability."""
    try:
        sys.exit(main())
    except SystemExit as e:
        sys.exit(e.code)
    except Exception as e:
        logger.exception(f"An unexpected error occurred in the CLI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    entry_point()
