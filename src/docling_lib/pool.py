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
    DOCLING_MAX_WORKERS,
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
            options = DocumentConversionOptions.from_dict(options_dict)
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
    options = DocumentConversionOptions.from_dict(options_dict)

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

                from .converter import DocumentConversionOptions

                # Retrieve default options for initializer preloading
                default_options_dict = DocumentConversionOptions().to_dict()

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
