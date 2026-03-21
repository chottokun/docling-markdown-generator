import argparse
import logging
import sys
from pathlib import Path

# Import from config and converter
from .config import (
    IMAGE_DIR_NAME,
    IMAGE_RESOLUTION_SCALE,
    MD_OUTPUT_NAME,
    setup_logging,
)
from .converter import process_pdf

# Configure logging for the CLI tool
logger = logging.getLogger(__name__)
setup_logging()


def main(args=None):
    """
    Main function for the command-line interface.
    Parses arguments and runs the high-accuracy document processing workflow.
    """
    parser = argparse.ArgumentParser(
        description="Extract markdown, figures, and tables from documents (PDF, DOCX, PPTX) with high accuracy."
    )
    parser.add_argument(
        "pdf_file", type=Path, help="Path to the input document file (PDF, DOCX, PPTX)."
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

    parsed_args = parser.parse_args(args if args is not None else sys.argv[1:])

    logger.info(f"Starting high-accuracy workflow for: {parsed_args.pdf_file}")

    # Call the new, unified processing function
    result_path = process_pdf(
        parsed_args.pdf_file,
        parsed_args.output_dir,
        image_dir_name=parsed_args.image_dir,
        md_output_name=parsed_args.output_name,
        image_scale=parsed_args.image_scale,
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