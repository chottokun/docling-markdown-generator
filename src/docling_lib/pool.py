import logging
import multiprocessing
import shutil
import tempfile
import threading
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .converter import DocumentConversionOptions, PDFConverter

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
    DOCLING_MAX_WORKERS,
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
)

logger = logging.getLogger(__name__)


class ThreadSafeModelPool:
    """
    Thread-safe model pool that caches up to 4 PDFConverter instances.
    Operates on a double-checked locking pattern (using threading.RLock)
    using the heavy converter configuration variables as the cache key.
    """

    def __init__(self, max_size: int = 4):
        self.max_size = max_size
        self._pool: dict[tuple, PDFConverter] = {}
        self._access_order: list[tuple] = []
        self._lock = threading.RLock()

    def get_converter(self, options: "DocumentConversionOptions") -> "PDFConverter":
        from .converter import PDFConverter

        # Create a unique hashable key from the heavy options
        key = (
            options.image_scale,
            options.do_formula,
            options.do_ocr,
            options.do_chart,
            options.do_code,
            options.table_format,
            options.num_threads,
            options.cuda_use_flash_attention,
        )

        with self._lock:
            if key in self._pool:
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)
                return self._pool[key]

        # Double-checked pattern: create new converter outside the lock to avoid blocking other threads
        converter = PDFConverter(options=options)

        with self._lock:
            if key in self._pool:
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)
                return self._pool[key]

            if len(self._pool) >= self.max_size:
                lru_key = self._access_order.pop(0)
                self._pool.pop(lru_key, None)

            self._pool[key] = converter
            self._access_order.append(key)
            return converter


def _worker_initializer(options_dict: dict | None = None) -> None:
    """
    Initializes a worker process by pre-loading the PDFConverter model cache.
    """
    if options_dict:
        try:
            from .converter import DocumentConversionOptions, _get_or_create_converter

            # Recreate options and get converter to trigger lazy preloading
            options = DocumentConversionOptions(**options_dict)
            _get_or_create_converter(options)
        except Exception as e:
            # Don't crash worker startup if pre-loading fails, just log
            logger.warning(f"Worker preload initialization failed: {e}")


def process_pdf_multi_process_worker(
    pdf_path_str: str,
    output_dir_str: str,
    options_dict: dict,
) -> str | None:
    """
    Task function that runs in a worker process.
    Uses tempfile.TemporaryDirectory to manage task-level files safely.
    """
    from .converter import DocumentConversionOptions, process_pdf

    pdf_path = Path(pdf_path_str)
    output_dir = Path(output_dir_str)
    options = DocumentConversionOptions(**options_dict)

    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir) as temp_dir_name:
        temp_dir = Path(temp_dir_name)

        # Copy input PDF to the isolated temp directory to protect original path I/O
        temp_pdf_path = temp_dir / pdf_path.name
        shutil.copy2(pdf_path, temp_pdf_path)

        # Define isolated temp output dir
        temp_output_dir = temp_dir / "output"
        temp_output_dir.mkdir(parents=True, exist_ok=True)

        # Execute the actual conversion
        res_path = process_pdf(
            pdf_path=temp_pdf_path,
            output_dir=temp_output_dir,
            options=options,
        )

        if res_path is not None:
            # Copy all generated files (markdown, images) to the final output directory
            output_dir.mkdir(parents=True, exist_ok=True)
            for item in temp_output_dir.iterdir():
                if item.is_dir():
                    shutil.copytree(item, output_dir / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, output_dir / item.name)
            return str(output_dir / res_path.name)

        return None


_process_pool: ProcessPoolExecutor | None = None
_process_pool_lock = threading.Lock()


def get_process_pool() -> ProcessPoolExecutor:
    """
    Returns the thread-safe global ProcessPoolExecutor.
    Lazily initializes the process pool using the 'spawn' start method.
    """
    global _process_pool
    if _process_pool is None:
        with _process_pool_lock:
            if _process_pool is None:
                ctx = multiprocessing.get_context("spawn")

                # Retrieve default options for initializer preloading
                default_options_dict = {
                    "image_dir_name": IMAGE_DIR_NAME,
                    "md_output_name": MD_OUTPUT_NAME,
                    "image_scale": IMAGE_RESOLUTION_SCALE,
                    "table_format": DOCLING_TABLE_FORMAT,
                    "do_formula": DO_FORMULA,
                    "do_ocr": DO_OCR,
                    "do_chart": DO_CHART,
                    "do_code": DO_CODE,
                    "include_page_breaks": DOCLING_INCLUDE_PAGE_BREAKS,
                    "include_kv_extraction": DOCLING_INCLUDE_KV_EXTRACTION,
                    "vlm_enabled": DOCLING_VLM_ENABLED,
                    "vlm_provider": DOCLING_VLM_PROVIDER,
                    "vlm_api_key": DOCLING_VLM_API_KEY,
                    "vlm_model": DOCLING_VLM_MODEL,
                    "vlm_endpoint": DOCLING_VLM_ENDPOINT,
                    "vlm_prompt": DOCLING_VLM_PROMPT,
                    "vlm_max_concurrent": DOCLING_VLM_MAX_CONCURRENT,
                    "num_threads": DOCLING_NUM_THREADS,
                    "cuda_use_flash_attention": DOCLING_CUDA_FLASH_ATTENTION,
                    "math_inline_delim": DOCLING_MATH_INLINE_DELIM,
                    "math_block_delim": DOCLING_MATH_BLOCK_DELIM,
                    "math_block_newline": DOCLING_MATH_BLOCK_NEWLINE,
                }

                _process_pool = ProcessPoolExecutor(
                    max_workers=DOCLING_MAX_WORKERS,
                    mp_context=ctx,
                    initializer=_worker_initializer,
                    initargs=(default_options_dict,),
                )
    return _process_pool


def shutdown_process_pool() -> None:
    """
    Shuts down the global ProcessPoolExecutor.
    """
    global _process_pool
    with _process_pool_lock:
        if _process_pool is not None:
            _process_pool.shutdown(wait=True)
            _process_pool = None
