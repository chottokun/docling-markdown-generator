import logging
from pathlib import Path
from typing import Optional

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
    WordFormatOption,
    PowerpointFormatOption,
)
from docling_core.types.doc import ImageRefMode

from .config import MD_OUTPUT_NAME, IMAGE_DIR_NAME, IMAGE_RESOLUTION_SCALE

# Configure logging
logger = logging.getLogger(__name__)


class PDFConverter:
    """
    A class to manage a reusable DocumentConverter instance for performance.
    """

    def __init__(self, image_scale: float = IMAGE_RESOLUTION_SCALE):
        pipeline_options = PdfPipelineOptions()
        pipeline_options.generate_picture_images = True
        pipeline_options.images_scale = image_scale

        self.doc_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
                InputFormat.DOCX: WordFormatOption(),
                InputFormat.PPTX: PowerpointFormatOption(),
            }
        )
        self.image_scale = image_scale

    def convert(
        self,
        input_path: Path,
        output_dir: Path,
        image_dir_name: str = IMAGE_DIR_NAME,
        md_output_name: str = MD_OUTPUT_NAME,
    ) -> Optional[Path]:
        """
        Converts the document to Markdown and extracts images.
        """
        try:
            # Perform conversion
            result = self.doc_converter.convert(input_path)
            doc = result.document

            # Create output directory
            output_dir.mkdir(parents=True, exist_ok=True)
            images_dir = output_dir / image_dir_name
            images_dir.mkdir(parents=True, exist_ok=True)

            # Metadata should be preserved by docling itself in the document object
            # Save as markdown
            md_path = output_dir / md_output_name
            doc.save_as_markdown(
                filename=md_path,
                artifacts_dir=images_dir,
                image_mode=ImageRefMode.REFERENCED,
            )

            logger.info(f"Successfully processed {input_path}")
            return md_path

        except (OSError, PermissionError) as e:
            # Propagate OSError and PermissionError as per instruction
            raise e
        except Exception as e:
            logger.error(f"Error converting document {input_path}: {e}")
            return None


# Global shared converter instance for reuse
_default_pdf_converter: Optional[PDFConverter] = None


def process_pdf(
    pdf_path: Path,
    output_dir: Path,
    image_dir_name: str = IMAGE_DIR_NAME,
    md_output_name: str = MD_OUTPUT_NAME,
    image_scale: float = IMAGE_RESOLUTION_SCALE,
    converter: Optional[DocumentConverter] = None,
) -> Optional[Path]:
    """
    High-level function to process a document (PDF, DOCX, etc.).
    """
    # 1. Input Validation
    if not pdf_path.exists():
        logger.error(f"Input file not found: {pdf_path}")
        return None

    # 2. Security Check: Path Traversal
    try:
        Path(output_dir).resolve()
        # Broad traversal check
        if ".." in output_dir.parts:
             logger.error(f"Security Error: Traversal detected in output directory {output_dir}")
             return None
            
    except Exception as e:
        logger.error(f"Security Error during path resolution: {e}")
        return None

    # 3. Processing
    try:
        if converter:
            # Use explicit converter (already configured)
            result = converter.convert(pdf_path)
            doc = result.document

            output_dir.mkdir(parents=True, exist_ok=True)
            images_dir = output_dir / image_dir_name
            images_dir.mkdir(parents=True, exist_ok=True)

            md_path = output_dir / md_output_name
            doc.save_as_markdown(
                filename=md_path,
                artifacts_dir=images_dir,
                image_mode=ImageRefMode.REFERENCED,
            )
            return md_path

        global _default_pdf_converter
        # Optimization: use own stored image_scale if available to avoid accessing internal mock in tests
        if (
            _default_pdf_converter is None
            or _default_pdf_converter.image_scale != image_scale
        ):
            _default_pdf_converter = PDFConverter(image_scale=image_scale)

        return _default_pdf_converter.convert(
            pdf_path, output_dir, image_dir_name, md_output_name
        )

    except (OSError, PermissionError) as e:
        logger.error(f"Could not create output directory: {e}")
        return None
    except Exception as e:
        logger.error(f"Workflow Error: {e}")
        return None
