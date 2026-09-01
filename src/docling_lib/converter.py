import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor as ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import (
    DocumentConverter,
    EmailFormatOption,
    EpubFormatOption,
    ExcelFormatOption,
    HTMLFormatOption,
    ImageFormatOption,
    LatexFormatOption,
    MarkdownFormatOption,
    PdfFormatOption,
    PowerpointFormatOption,
    WordFormatOption,
    XBRLFormatOption,
)
from docling_core.transforms.serializer.markdown import (
    MarkdownParams,
)
from docling_core.types.doc import (
    DoclingDocument,
    ImageRefMode,
)

from .config import (
    DO_CHART,
    DO_CODE,
    DO_FORMULA,
    DO_OCR,
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
    USE_GPU,
)
from .pool import (
    ThreadSafeModelPool as ThreadSafeModelPool,
)
from .pool import (
    _worker_initializer as _worker_initializer,
)
from .pool import (
    get_process_pool as get_process_pool,
)
from .pool import (
    process_pdf_multi_process_worker as process_pdf_multi_process_worker,
)
from .pool import (
    shutdown_process_pool as shutdown_process_pool,
)
from .serializers import (
    PAGE_BREAK_RE as PAGE_BREAK_RE,
)
from .serializers import (
    CustomMarkdownPictureSerializer as CustomMarkdownPictureSerializer,
)
from .serializers import (
    EnhancedMarkdownSerializer as EnhancedMarkdownSerializer,
)
from .serializers import (
    EnhancedMarkdownTextSerializer as EnhancedMarkdownTextSerializer,
)
from .serializers import (
    HTMLTableMarkdownSerializer as HTMLTableMarkdownSerializer,
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
            device = torch.device("cuda")
            # Verify compute capability compatibility
            major, minor = torch.cuda.get_device_capability(device)
            capability = major + minor / 10.0
            # Modern PyTorch builds usually require CC >= 7.5. Older GPUs like GTX 1060 (sm_61)
            # are incompatible with current PyTorch installations and will cause errors/hangs during model runs.
            if capability < 7.5:
                logger.warning(
                    f"GPU compute capability {capability} (sm_{major}{minor}) is less than required 7.5. "
                    "Falling back to CPU."
                )
                return False

            # Run a dummy tensor operation to verify execution capability
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
    table_format: str = DOCLING_TABLE_FORMAT
    do_formula: bool = DO_FORMULA
    do_ocr: bool = DO_OCR
    do_chart: bool = DO_CHART  # New in docling v2.x
    do_code: bool = DO_CODE  # New in docling v2.x
    include_page_breaks: bool = (
        DOCLING_INCLUDE_PAGE_BREAKS  # New for RAG: inject page markers
    )
    include_kv_extraction: bool = (
        DOCLING_INCLUDE_KV_EXTRACTION  # New for RAG: extract KV pairs
    )
    vlm_enabled: bool = DOCLING_VLM_ENABLED
    vlm_provider: str = DOCLING_VLM_PROVIDER
    vlm_api_key: str = DOCLING_VLM_API_KEY
    vlm_model: str = DOCLING_VLM_MODEL
    vlm_endpoint: str = DOCLING_VLM_ENDPOINT
    vlm_prompt: str = DOCLING_VLM_PROMPT
    vlm_max_concurrent: int = DOCLING_VLM_MAX_CONCURRENT
    num_threads: int = DOCLING_NUM_THREADS
    cuda_use_flash_attention: bool = DOCLING_CUDA_FLASH_ATTENTION
    math_inline_delim: str = DOCLING_MATH_INLINE_DELIM
    math_block_delim: str = DOCLING_MATH_BLOCK_DELIM
    math_block_newline: Any = DOCLING_MATH_BLOCK_NEWLINE


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

        if self.options.include_page_breaks:
            pipeline_options.generate_page_images = True
            pipeline_options.generate_parsed_pages = True

        # Configure accelerator options (GPU fallback to CPU)
        if is_cuda_compatible():
            acc_device = AcceleratorDevice.AUTO
        else:
            acc_device = AcceleratorDevice.CPU

        pipeline_options.accelerator_options = AcceleratorOptions(
            device=acc_device,
            num_threads=self.options.num_threads,
            cuda_use_flash_attention2=self.options.cuda_use_flash_attention,
        )

        # Configure DocumentConverter with multi-format support
        format_options = self._get_format_options(pipeline_options)

        self.doc_converter = DocumentConverter(format_options=format_options)

    def _get_format_options(self, pipeline_options: PdfPipelineOptions) -> dict:
        """
        Constructs the format options dictionary.
        """
        return {
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            InputFormat.DOCX: WordFormatOption(pipeline_options=pipeline_options),
            InputFormat.PPTX: PowerpointFormatOption(pipeline_options=pipeline_options),
            InputFormat.XLSX: ExcelFormatOption(pipeline_options=pipeline_options),
            InputFormat.HTML: HTMLFormatOption(pipeline_options=pipeline_options),
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options),
            InputFormat.MD: MarkdownFormatOption(pipeline_options=pipeline_options),
            InputFormat.EMAIL: EmailFormatOption(pipeline_options=pipeline_options),
            InputFormat.EPUB: EpubFormatOption(pipeline_options=pipeline_options),
            InputFormat.LATEX: LatexFormatOption(pipeline_options=pipeline_options),
            InputFormat.XML_XBRL: XBRLFormatOption(pipeline_options=pipeline_options),
            InputFormat.VTT: HTMLFormatOption(pipeline_options=pipeline_options),
        }

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

    def _prefetch_vlm_captions(
        self, doc: DoclingDocument, actual_options: DocumentConversionOptions
    ) -> dict[str, str]:
        """
        Prefetch VLM captions for all pictures in the document in parallel using ThreadPoolExecutor.
        """
        vlm_captions: dict[str, str] = {}
        if not actual_options.vlm_enabled or not doc.pictures:
            return vlm_captions

        from concurrent.futures import ThreadPoolExecutor

        from .vlm import generate_caption_sync

        def fetch_task(item):
            if item.image and item.image.pil_image:
                try:
                    caption = generate_caption_sync(
                        image=item.image.pil_image,
                        provider=actual_options.vlm_provider,
                        api_key=actual_options.vlm_api_key,
                        model=actual_options.vlm_model,
                        endpoint=actual_options.vlm_endpoint,
                        prompt=actual_options.vlm_prompt,
                        vlm_max_concurrent=actual_options.vlm_max_concurrent,
                    )
                    return item.self_ref, caption
                except Exception as e:
                    logger.warning(
                        f"Failed to prefetch VLM caption for {item.self_ref}: "
                        f"{sanitize_log_message(e)}"
                    )
            return item.self_ref, ""

        def is_valid_image(item) -> bool:
            if not item.image:
                return False
            try:
                return item.image.pil_image is not None
            except Exception as e:
                logger.warning(
                    f"Skipping VLM prefetch for {item.self_ref} because image could not be loaded: "
                    f"{sanitize_log_message(e)}"
                )
                return False

        # We filter out items without valid images to avoid submitting empty tasks
        valid_items = [item for item in doc.pictures if is_valid_image(item)]
        if not valid_items:
            return vlm_captions

        if len(valid_items) == 1:
            # Sequential execution for single-image documents to avoid threadpool overhead
            self_ref, caption = fetch_task(valid_items[0])
            if caption:
                vlm_captions[self_ref] = caption
        else:
            # Parallel execution, bounded by vlm_max_concurrent and capped at 32
            max_workers = min(len(valid_items), actual_options.vlm_max_concurrent, 32)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = executor.map(fetch_task, valid_items)
                for self_ref, caption in results:
                    if caption:
                        vlm_captions[self_ref] = caption

        return vlm_captions

    def _serialize_to_markdown(
        self,
        doc: DoclingDocument,
        table_format: str,
        options: DocumentConversionOptions | None = None,
        image_tag_template: str | None = None,
        slug: str | None = None,
    ) -> str:
        """
        Serializes the document to Markdown using the enhanced serializer.
        """
        actual_options = options or self.options

        # 1. Prefetch VLM captions in parallel
        vlm_captions = self._prefetch_vlm_captions(doc, actual_options)

        # 2. Configure enhanced custom serializer
        serializer = EnhancedMarkdownSerializer(
            doc=doc,
            table_format=table_format,
            vlm_enabled=actual_options.vlm_enabled,
            vlm_provider=actual_options.vlm_provider,
            vlm_api_key=actual_options.vlm_api_key,
            vlm_model=actual_options.vlm_model,
            vlm_endpoint=actual_options.vlm_endpoint,
            vlm_prompt=actual_options.vlm_prompt,
            vlm_max_concurrent=actual_options.vlm_max_concurrent,
            vlm_captions=vlm_captions,
            image_dir_name=actual_options.image_dir_name,
            image_tag_template=image_tag_template,
            slug=slug,
            math_inline_delim=actual_options.math_inline_delim,
            math_block_delim=actual_options.math_block_delim,
            math_block_newline=actual_options.math_block_newline,
            params=MarkdownParams(
                image_mode=ImageRefMode.REFERENCED,
                image_placeholder="<!-- image -->",
                page_break_placeholder="<!-- PAGE_BREAK_MARKER -->"
                if actual_options.include_page_breaks
                else None,
            ),
        )

        # Serialize
        ser_res = serializer.serialize()
        return ser_res.text

    def _apply_metadata_frontmatter(
        self,
        doc: DoclingDocument,
        md_content: str,
        options: DocumentConversionOptions | None = None,
    ) -> str:
        """
        Adds metadata as YAML frontmatter to the Markdown content if available.
        """
        actual_options = options or self.options
        metadata = {}
        if doc.name:
            # Sanitize doc.name to prevent YAML frontmatter injection
            metadata["title"] = doc.name.replace("\n", " ").replace("\r", " ")

        # Add more RAG-specific metadata
        if hasattr(doc, "num_pages") and callable(doc.num_pages):
            try:
                page_count = doc.num_pages()
                if page_count > 0:
                    metadata["page_count"] = page_count
            except Exception as e:
                logger.warning(
                    f"Failed to extract page count: {sanitize_log_message(e)}"
                )

        if metadata:
            import yaml

            # default_flow_style=False ensures it doesn't use {key: value} block style
            # which might have caused some assertion issues with quoting
            yaml_frontmatter = yaml.dump(
                metadata, allow_unicode=True, default_flow_style=False
            ).strip()
            md_content = f"---\n{yaml_frontmatter}\n---\n\n{md_content}"

        # Inject Key Information section if requested
        if actual_options.include_kv_extraction:
            kv_section = "\n\n## Key Information\n<!-- KV_START -->\n"
            # In a real implementation, this would use an LLM or specific heuristics
            # Here we provide a placeholder as a foundation
            kv_section += "- **Extraction Status**: Placeholder (Requires VLM/LLM)\n"
            kv_section += "<!-- KV_END -->\n"
            md_content = kv_section + md_content

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
            doc=doc, table_format=actual_options.table_format, options=actual_options
        )

        # 4. Post-processing (RAG optimizations)
        if actual_options.include_page_breaks:
            # Prepend the page break marker for Page 1 if it is not already present
            if not md_content.strip().startswith("<!-- PAGE_BREAK: Page 1 -->"):
                md_content = "<!-- PAGE_BREAK: Page 1 -->\n\n" + md_content

        # 5. Metadata / Frontmatter
        md_content = self._apply_metadata_frontmatter(
            doc=doc, md_content=md_content, options=actual_options
        )

        # 6. Save images
        self._save_images(doc, resolved_images_dir)

        # 7. Save output
        self._write_markdown_file(resolved_md_path, md_content)

        return output_dir / md_output_name

    def _save_images(self, doc: DoclingDocument, images_dir: Path) -> None:
        """
        Saves images extracted from the document to the specified directory.
        """
        valid_pictures = [
            (i, element)
            for i, element in enumerate(doc.pictures)
            if element.image and element.image.pil_image
        ]

        if not valid_pictures:
            return

        def save_image(i, element):
            image_filename = f"picture_{i + 1}.png"
            image_path = images_dir / image_filename
            try:
                element.image.pil_image.save(image_path)
                logger.debug(f"Saved image: {image_path}")
            except Exception as e:
                logger.warning(
                    f"Failed to save image {image_path}: {sanitize_log_message(e)}"
                )

        if len(valid_pictures) == 1:
            # Sequential execution for single-image documents to avoid threadpool overhead
            i, element = valid_pictures[0]
            save_image(i, element)
        else:
            # Parallel execution for multi-image files, dynamically bounding workers
            max_workers = min(len(valid_pictures), 32)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for i, element in valid_pictures:
                    executor.submit(save_image, i, element)


class EnhancedDoclingConverter:
    """
    Enhanced Docling Converter wrapper that produces customized image tags
    using custom templates (e.g. `![[assets/{slug}/{image_name}]]`)
    and allows extracting/saving images directly to a specified directory.
    """

    def __init__(self, docling_converter: PDFConverter | None = None):
        self.docling_converter = docling_converter or PDFConverter()

    def convert_to_markdown(
        self,
        input_path: Path,
        slug: str | None = None,
        image_tag_template: str = "![{image_name}](assets/{slug}/{image_name})",
        assets_dir: Path | None = None,
    ) -> str:
        """
        Converts document at input_path and returns the markdown text with formatted image tags.
        If assets_dir is provided, saves images in that directory.
        """
        input_path = Path(input_path)
        # 1. Convert input document using docling_converter
        result = self.docling_converter.doc_converter.convert(input_path)
        doc = result.document

        # 2. Determine slug: prioritize explicit slug, then assets_dir.name, then generated slug from filename
        if slug is None:
            if assets_dir is not None:
                slug = assets_dir.name
            else:
                raw_slug = input_path.stem.lower()
                # Replace non-alphanumeric characters with hyphens
                slug = re.sub(r"[^a-z0-9]+", "-", raw_slug).strip("-")
                if not slug:
                    slug = "document"

        # 3. Save images to assets_dir if provided
        if assets_dir is not None:
            assets_dir = Path(assets_dir)
            assets_dir.mkdir(parents=True, exist_ok=True)
            self.docling_converter._save_images(doc, assets_dir)

        # 4. Render the document with custom image tags
        return self._render_with_image_tags(doc, template=image_tag_template, slug=slug)

    def _render_with_image_tags(
        self, doc: DoclingDocument, template: str, slug: str
    ) -> str:
        """
        Renders the document's structure to Markdown text using CustomMarkdownPictureSerializer
        with custom template and slug.
        """
        # We invoke the internal _serialize_to_markdown of docling_converter
        md_content = self.docling_converter._serialize_to_markdown(
            doc=doc,
            table_format=self.docling_converter.options.table_format,
            options=self.docling_converter.options,
            image_tag_template=template,
            slug=slug,
        )

        # Post-process page breaks if required by options
        if self.docling_converter.options.include_page_breaks:
            if not md_content.strip().startswith("<!-- PAGE_BREAK: Page 1 -->"):
                md_content = "<!-- PAGE_BREAK: Page 1 -->\n\n" + md_content

        # Apply metadata frontmatter if available
        md_content = self.docling_converter._apply_metadata_frontmatter(
            doc=doc,
            md_content=md_content,
            options=self.docling_converter.options,
        )

        return md_content


# Thread-safe model pool for reuse
_model_pool = ThreadSafeModelPool(max_size=4)
_converter_lock = threading.Lock()
_default_pdf_converter: PDFConverter | None = None


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
    Manages and retrieves a cached PDFConverter instance from the model pool.
    """
    global _default_pdf_converter
    if _default_pdf_converter is None:
        _model_pool._pool.clear()
        _model_pool._access_order.clear()

    _default_pdf_converter = _model_pool.get_converter(options)
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


__all__ = [
    "PDFConverter",
    "DocumentConversionOptions",
    "process_pdf",
    "EnhancedDoclingConverter",
    "CustomMarkdownPictureSerializer",
    "EnhancedMarkdownTextSerializer",
    "HTMLTableMarkdownSerializer",
    "EnhancedMarkdownSerializer",
    "ThreadSafeModelPool",
    "_worker_initializer",
    "process_pdf_multi_process_worker",
    "get_process_pool",
    "shutdown_process_pool",
    "PAGE_BREAK_RE",
    "is_cuda_compatible",
]
