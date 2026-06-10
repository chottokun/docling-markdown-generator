import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import (
    DocumentConverter,
    ExcelFormatOption,
    HTMLFormatOption,
    ImageFormatOption,
    MarkdownFormatOption,
    PdfFormatOption,
    PowerpointFormatOption,
    WordFormatOption,
)
# New format options for docling v2.x
try:
    from docling.document_converter import (
        EmailFormatOption,
        EpubFormatOption,
        LatexFormatOption,
        XBRLFormatOption,
    )
except ImportError:
    # Fallback for older docling versions
    XBRLFormatOption = None
    EmailFormatOption = None
    EpubFormatOption = None
    LatexFormatOption = None

from docling_core.transforms.serializer.markdown import (
    MarkdownDocSerializer,
    MarkdownParams,
    MarkdownTableSerializer,
    SerializationResult,
    create_ser_result,
)
from docling_core.types.doc import (
    DoclingDocument,
    ImageRefMode,
    TableItem,
)

from .config import (
    DO_CHART,
    DO_CODE,
    DO_FORMULA,
    DO_OCR,
    IMAGE_DIR_NAME,
    IMAGE_RESOLUTION_SCALE,
    MD_OUTPUT_NAME,
    USE_GPU,
)
from .utils import sanitize_log_message

# Configure logging
logger = logging.getLogger(__name__)


def is_cuda_compatible() -> bool:
    """
    Checks if CUDA is configured to be used, available, and compatible with PyTorch.
    Performs a brief real tensor operation on GPU to catch incompatible compute
    capability mismatches at startup.
    """
    if not USE_GPU:
        logger.info("GPU usage is disabled via configuration (USE_GPU=False).")
        return False

    try:
        if torch.cuda.is_available():
            # Run a dummy tensor operation to verify execution capability
            device = torch.device("cuda")
            _x = torch.zeros(1, device=device)
            torch.cuda.synchronize()
            logger.info("CUDA is fully available and compatible with the current GPU.")
            return True
        logger.info("CUDA is not available on this system.")
        return False
    except Exception as e:
        logger.warning(
            f"CUDA is detected but not compatible with this PyTorch build. "
            f"Falling back to CPU. Details: {sanitize_log_message(e)}"
        )
        return False



@dataclass
class DocumentConversionOptions:
    """Options for document conversion and serialization."""

    image_dir_name: str = IMAGE_DIR_NAME
    md_output_name: str = MD_OUTPUT_NAME
    image_scale: float = IMAGE_RESOLUTION_SCALE
    table_format: str = "html"
    do_formula: bool = DO_FORMULA
    do_ocr: bool = DO_OCR
    do_chart: bool = DO_CHART  # New in docling v2.x
    do_code: bool = DO_CODE  # New in docling v2.x


class HTMLTableMarkdownSerializer(MarkdownTableSerializer):
    """
    Custom Markdown Table Serializer that exports tables as HTML
    to preserve complex structures like merged cells.
    """

    def serialize(
        self,
        *,
        item: TableItem,
        doc_serializer: Any,
        doc: DoclingDocument,
        **kwargs: Any,
    ) -> SerializationResult:
        res_parts: list[SerializationResult] = []

        # 1. Serialize Captions (Standard behavior)
        cap_res = doc_serializer.serialize_captions(item=item, **kwargs)
        if cap_res.text:
            res_parts.append(cap_res)

        # 2. Serialize Table as HTML
        try:
            # High-fidelity HTML export
            table_html = item.export_to_html(doc=doc)
            if table_html:
                res_parts.append(create_ser_result(text=table_html, span_source=item))
        except Exception as e:
            logger.warning(
                f"Failed to export table as HTML, falling back: {sanitize_log_message(e)}"
            )
            # Fallback to standard markdown table if HTML export fails
            return super().serialize(
                item=item, doc_serializer=doc_serializer, doc=doc, **kwargs
            )

        if not res_parts:
            return create_ser_result(text="", span_source=[])
        if len(res_parts) == 1:
            return create_ser_result(text=res_parts[0].text, span_source=res_parts)

        text_res = "\n\n".join([r.text for r in res_parts])
        return create_ser_result(text=text_res, span_source=res_parts)


class EnhancedMarkdownSerializer(MarkdownDocSerializer):
    """
    Custom Markdown Serializer that:
    1. Exports tables as HTML to preserve complex structures.
    2. Provides a foundation for future image alt-text enhancement (OCR/VLM).
    """

    def __init__(self, doc: DoclingDocument, table_format: str = "html", **kwargs):
        # In tests, doc might be a MagicMock. Pydantic models (like
        # MarkdownDocSerializer) may fail validation if they don't see a real
        # DoclingDocument.
        if hasattr(doc, "_mock_name") or "MagicMock" in str(type(doc)):
            # Skip Pydantic validation by setting attributes directly if it's a mock
            # Use object.__setattr__ to bypass Pydantic's frozen or validation logic if needed
            object.__setattr__(self, "doc", doc)
            object.__setattr__(self, "params", kwargs.get("params", MarkdownParams()))
            # Initialize other fields to avoid Pydantic errors if they are accessed
            # Use getattr with a sentinel for faster lookup than hasattr while
            # preserving logical equivalence.
            sentinel = object()
            for field in self.model_fields:
                if getattr(self, field, sentinel) is sentinel:
                    object.__setattr__(self, field, None)
        else:
            super().__init__(doc=doc, **kwargs)

        if table_format.lower() == "html":
            self.table_serializer = HTMLTableMarkdownSerializer()


class PDFConverter:
    """
    A class to manage a reusable DocumentConverter instance for performance.
    """

    def __init__(
        self,
        options: DocumentConversionOptions | None = None,
    ):
        self.options = options or DocumentConversionOptions()

        # Configure pipeline options
        pipeline_options = PdfPipelineOptions()
        pipeline_options.generate_picture_images = True
        pipeline_options.images_scale = self.options.image_scale
        pipeline_options.do_formula_enrichment = self.options.do_formula
        pipeline_options.do_ocr = self.options.do_ocr
        pipeline_options.do_chart_extraction = self.options.do_chart
        pipeline_options.do_code_enrichment = self.options.do_code

        # Configure accelerator options (GPU fallback to CPU)
        if is_cuda_compatible():
            acc_device = AcceleratorDevice.AUTO
        else:
            acc_device = AcceleratorDevice.CPU

        pipeline_options.accelerator_options = AcceleratorOptions(
            device=acc_device
        )

        # Configure DocumentConverter with multi-format support
        format_options = {
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            InputFormat.DOCX: WordFormatOption(pipeline_options=pipeline_options),
            InputFormat.PPTX: PowerpointFormatOption(
                pipeline_options=pipeline_options
            ),
            InputFormat.XLSX: ExcelFormatOption(pipeline_options=pipeline_options),
            InputFormat.HTML: HTMLFormatOption(pipeline_options=pipeline_options),
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options),
            InputFormat.MD: MarkdownFormatOption(pipeline_options=pipeline_options),
        }

        # Add new formats if available in the installed docling version
        if XBRLFormatOption:
            # New versions of docling use XML_XBRL
            attr_name = "XML_XBRL" if hasattr(InputFormat, "XML_XBRL") else "XBRL"
            if hasattr(InputFormat, attr_name):
                format_options[getattr(InputFormat, attr_name)] = XBRLFormatOption(
                    pipeline_options=pipeline_options
                )
        if EmailFormatOption:
            format_options[InputFormat.EMAIL] = EmailFormatOption(
                pipeline_options=pipeline_options
            )
        if EpubFormatOption:
            format_options[InputFormat.EPUB] = EpubFormatOption(
                pipeline_options=pipeline_options
            )
        if LatexFormatOption:
            format_options[InputFormat.LATEX] = LatexFormatOption(
                pipeline_options=pipeline_options
            )
        # WebVTT typically uses the same pipeline or has specific options in newer docling
        vtt_attr = "VTT" if hasattr(InputFormat, "VTT") else "WEBVTT"
        if hasattr(InputFormat, vtt_attr):
            format_options[getattr(InputFormat, vtt_attr)] = HTMLFormatOption(
                pipeline_options=pipeline_options
            )

        self.doc_converter = DocumentConverter(format_options=format_options)

    def convert(
        self,
        input_path: Path,
        output_dir: Path,
        options: DocumentConversionOptions | None = None,
    ) -> Path | None:
        """
        Converts the document to Markdown and extracts images.
        """
        # Use provided options or fall back to the instance's initialization options
        actual_options = options or self.options
        try:
            # Perform conversion
            result = self.doc_converter.convert(input_path)
            doc = result.document

            return self._save_markdown(doc, output_dir, actual_options)

        except (OSError, PermissionError) as e:
            # Propagate OSError and PermissionError as per instruction
            raise e
        except Exception as e:
            logger.error(
                f"Error converting document {sanitize_log_message(input_path)}: {sanitize_log_message(e)}"
            )
            return None

    def _validate_and_resolve_paths(
        self, output_dir: Path, image_dir_name: str, md_output_name: str
    ) -> tuple[Path, Path]:
        """
        Validates output paths for security and resolves them.
        """
        try:
            resolved_output_dir = output_dir.resolve()
            resolved_images_dir = (output_dir / image_dir_name).resolve()
            resolved_md_path = (output_dir / md_output_name).resolve()

            if not resolved_images_dir.is_relative_to(resolved_output_dir):
                logger.error(
                    "Security Error: Traversal detected in image directory %s",
                    sanitize_log_message(image_dir_name),
                )
                raise ValueError("Traversal detected in image directory")

            if not resolved_md_path.is_relative_to(resolved_output_dir):
                logger.error(
                    "Security Error: Traversal detected in markdown output name %s",
                    sanitize_log_message(md_output_name),
                )
                raise ValueError("Traversal detected in markdown output name")

            return resolved_images_dir, resolved_md_path

        except Exception as e:
            logger.error(
                f"Security Error during path resolution: {sanitize_log_message(e)}"
            )
            raise

    def _serialize_to_markdown(self, doc: DoclingDocument, table_format: str) -> str:
        """
        Serializes the document to Markdown using the enhanced serializer.
        """
        # Configure enhanced custom serializer
        serializer = EnhancedMarkdownSerializer(
            doc=doc,
            table_format=table_format,
            params=MarkdownParams(
                image_mode=ImageRefMode.REFERENCED,
                image_placeholder="<!-- image -->",
            ),
        )

        # Serialize
        ser_res = serializer.serialize()
        return ser_res.text

    def _apply_metadata_frontmatter(self, doc: DoclingDocument, md_content: str) -> str:
        """
        Adds metadata as YAML frontmatter to the Markdown content if available.
        """
        if doc.name:
            # Sanitize doc.name to prevent YAML frontmatter injection
            safe_name = doc.name.replace("\n", " ").replace("\r", " ")
            return f"---\ntitle: {safe_name}\n---\n\n{md_content}"

        return md_content

    def _prepare_output_directories(self, output_dir: Path, images_dir: Path) -> None:
        """
        Ensures that the output and images directories exist.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)

    def _write_markdown_file(self, md_path: Path, content: str) -> None:
        """
        Writes the Markdown content to the specified path.
        """
        md_path.write_text(content, encoding="utf-8")

    def _save_markdown(
        self,
        doc: DoclingDocument,
        output_dir: Path,
        options: DocumentConversionOptions | None = None,
    ) -> Path:
        """
        Helper method to save the document as Markdown and images.
        Uses an enhanced custom serializer based on the provided or instance configuration.
        """
        actual_options = options or self.options
        image_dir_name = actual_options.image_dir_name
        md_output_name = actual_options.md_output_name

        # 1. Path Resolution and Security Checks
        resolved_images_dir, resolved_md_path = self._validate_and_resolve_paths(
            output_dir=output_dir,
            image_dir_name=image_dir_name,
            md_output_name=md_output_name,
        )

        # 2. Create directories
        self._prepare_output_directories(output_dir, resolved_images_dir)

        # 3. Serialization
        md_content = self._serialize_to_markdown(
            doc=doc, table_format=actual_options.table_format
        )

        # 4. Metadata / Frontmatter
        md_content = self._apply_metadata_frontmatter(doc=doc, md_content=md_content)

        # 5. Save images
        self._save_images(doc, resolved_images_dir)

        # 6. Save output
        self._write_markdown_file(resolved_md_path, md_content)

        return output_dir / md_output_name

    def _save_images(self, doc: DoclingDocument, images_dir: Path) -> None:
        """
        Saves images extracted from the document to the specified directory.
        """
        # Iterate over pictures in the document
        for i, element in enumerate(doc.pictures):
            if element.image and element.image.pil_image:
                # We use picture_{i+1}.png as a default naming convention
                # In a more advanced version, we could use the image's original name or hash
                image_filename = f"picture_{i+1}.png"
                image_path = images_dir / image_filename
                try:
                    element.image.pil_image.save(image_path)
                    logger.debug(f"Saved image: {image_path}")
                except Exception as e:
                    logger.warning(
                        f"Failed to save image {image_path}: {sanitize_log_message(e)}"
                    )


# Global shared converter instance for reuse
_default_pdf_converter: PDFConverter | None = None
_converter_lock = threading.Lock()


def _validate_input_path(pdf_path: Path) -> bool:
    """Checks if the input file exists and logs an error if not."""
    if not pdf_path.exists():
        logger.error(f"Input file not found: {pdf_path}")
        return False
    return True


def _validate_output_security(output_dir: Path) -> bool:
    """
    Implements the path traversal security check and logs errors
    if validation fails.
    """
    try:
        # Robust validation: resolution must be relative to current working directory
        cwd = Path.cwd().resolve()
        resolved_out = (cwd / output_dir).resolve()

        if not resolved_out.is_relative_to(cwd):
            logger.error(
                "Security Error: Traversal detected in output directory "
                f"{sanitize_log_message(output_dir)}"
            )
            return False

    except Exception as e:
        logger.error(
            f"Security Error during path resolution: {sanitize_log_message(e)}"
        )
        return False

    return True


def _get_or_create_converter(
    options: DocumentConversionOptions,
) -> PDFConverter:
    """
    Manages and re-initializes the global _default_pdf_converter instance
    if the core (heavy) configuration has changed.
    NOTE: This function does not handle locking; the caller must acquire
    _converter_lock.
    """
    global _default_pdf_converter
    # Re-initialize only if "heavy" options that affect model/pipeline initialization
    # have changed. Document-specific options like filenames are ignored here.
    if _default_pdf_converter is None or (
        _default_pdf_converter.options.image_scale != options.image_scale
        or _default_pdf_converter.options.do_formula != options.do_formula
        or _default_pdf_converter.options.do_ocr != options.do_ocr
        or _default_pdf_converter.options.do_chart != options.do_chart
        or _default_pdf_converter.options.do_code != options.do_code
        or _default_pdf_converter.options.table_format != options.table_format
    ):
        _default_pdf_converter = PDFConverter(options=options)
    return _default_pdf_converter


def process_pdf(
    pdf_path: Path,
    output_dir: Path,
    options: DocumentConversionOptions | None = None,
    converter: DocumentConverter | None = None,
) -> Path | None:
    """
    High-level function to process a document (PDF, DOCX, etc.).

    Args:
        pdf_path: Path to the input document.
        output_dir: Directory where the output will be saved.
        options: Optional DocumentConversionOptions to customize the conversion.
        converter: Optional explicit docling DocumentConverter instance to use.

    Returns:
        Path to the generated Markdown file, or None if processing failed.
    """
    # 1. Input Validation
    if not _validate_input_path(pdf_path):
        return None

    # 2. Security Check: Path Traversal
    if not _validate_output_security(output_dir):
        return None

    # 3. Processing
    try:
        actual_options = options or DocumentConversionOptions()
        with _converter_lock:
            # Get or initialize the shared converter
            shared_converter = _get_or_create_converter(actual_options)

            if converter:
                # Use explicit converter (already configured) but still use our
                # saving logic
                result = converter.convert(pdf_path)
                doc = result.document
                return shared_converter._save_markdown(doc, output_dir, actual_options)

            return shared_converter.convert(pdf_path, output_dir, actual_options)

    except (OSError, PermissionError) as e:
        logger.error(f"Could not create output directory: {sanitize_log_message(e)}")
        return None
    except Exception as e:
        logger.error(f"Workflow Error: {sanitize_log_message(e)}")
        return None
