import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docling_lib.config import DOCLING_MAX_WORKERS
from docling_lib.converter import (
    _worker_initializer,
    get_process_pool,
    process_pdf_multi_process_worker,
    shutdown_process_pool,
)
from docling_lib.server import (
    get_concurrency_semaphore,
    get_dynamic_semaphore_limit,
)


def test_process_pool_initialization():
    """
    Verify that get_process_pool initializes the ProcessPoolExecutor
    and subsequent calls reuse the same pool instance.
    """
    # Shutdown any existing pool to start clean
    shutdown_process_pool()

    pool1 = get_process_pool()
    assert pool1 is not None

    pool2 = get_process_pool()
    assert pool1 is pool2  # Must be the same cached singleton pool

    shutdown_process_pool()


def test_worker_initializer_safe():
    """
    Verify that the worker process initializer executes safely without crashing
    even when given a sample options dictionary.
    """
    options_dict = {
        "image_dir_name": "images",
        "md_output_name": "processed_document.md",
        "image_scale": 2.0,
        "table_format": "html",
        "do_formula": False,
        "do_ocr": False,
        "do_chart": False,
        "do_code": False,
        "include_page_breaks": False,
        "include_kv_extraction": False,
        "vlm_enabled": False,
        "vlm_provider": "ollama",
        "vlm_api_key": "",
        "vlm_model": "qwen2-vl:2b",
        "vlm_endpoint": "http://localhost:11434",
        "vlm_prompt": "prompt",
        "vlm_max_concurrent": 1,
        "num_threads": 1,
        "cuda_use_flash_attention": False,
    }

    # Patch PDFConverter to avoid real ML initialization during unit test preloading
    with patch("docling_lib.converter.PDFConverter") as mock_converter:
        _worker_initializer(options_dict)
        mock_converter.assert_called_once()


def test_get_dynamic_semaphore_limit_psutil():
    """
    Verify that get_dynamic_semaphore_limit correctly calculates the concurrency limit
    using psutil.virtual_memory, honoring configured maximum workers.
    """
    # 1. Low memory scenario (e.g. 500 MB available) -> should limit to 1
    mock_mem_low = MagicMock()
    mock_mem_low.available = 500 * 1024 * 1024  # 500 MB
    with patch("psutil.virtual_memory", return_value=mock_mem_low):
        limit = get_dynamic_semaphore_limit()
        assert limit == 1

    # 2. Medium memory scenario (e.g. 3 GB available) -> should allow max(1, int(3/1.5)) = 2
    mock_mem_med = MagicMock()
    mock_mem_med.available = 3 * 1024 * 1024 * 1024  # 3 GB
    with (
        patch("psutil.virtual_memory", return_value=mock_mem_med),
        patch("docling_lib.config.DOCLING_MAX_WORKERS", 4),
    ):
        limit = get_dynamic_semaphore_limit()
        assert limit == 2

    # 3. High memory scenario (e.g. 16 GB available) -> should cap at max(2, DOCLING_MAX_WORKERS)
    mock_mem_high = MagicMock()
    mock_mem_high.available = 16 * 1024 * 1024 * 1024  # 16 GB
    with (
        patch("psutil.virtual_memory", return_value=mock_mem_high),
        patch("docling_lib.config.DOCLING_MAX_WORKERS", 2),
    ):
        limit = get_dynamic_semaphore_limit()
        # Cap is max(2, 2) = 2
        assert limit == 2

    # 4. Exception fallback scenario -> should default to max(1, DOCLING_MAX_WORKERS)
    with patch("psutil.virtual_memory", side_effect=Exception("mocked memory error")):
        limit = get_dynamic_semaphore_limit()
        assert limit == DOCLING_MAX_WORKERS


@pytest.mark.asyncio
async def test_get_concurrency_semaphore():
    """
    Verify that get_concurrency_semaphore returns an asyncio.Semaphore
    with the calculated limit.
    """
    import docling_lib.server

    docling_lib.server._concurrency_semaphore = None

    mock_mem = MagicMock()
    mock_mem.available = 6 * 1024 * 1024 * 1024  # 6 GB
    with (
        patch("psutil.virtual_memory", return_value=mock_mem),
        patch("docling_lib.config.DOCLING_MAX_WORKERS", 4),
    ):
        sem = await get_concurrency_semaphore()
        assert isinstance(sem, asyncio.Semaphore)
        assert sem is not None


def test_process_pdf_multi_process_worker_success(tmp_path):
    """
    Verify process_pdf_multi_process_worker copies temp files and returns valid output path on success.
    """
    input_file = tmp_path / "sample.pdf"
    input_file.write_text("%PDF-1.4 dummy content", encoding="utf-8")
    output_dir = tmp_path / "out"

    options_dict = {
        "image_dir_name": "images",
        "md_output_name": "processed_document.md",
        "image_scale": 2.0,
        "table_format": "html",
        "do_formula": False,
        "do_ocr": False,
        "do_chart": False,
        "do_code": False,
        "include_page_breaks": False,
        "include_kv_extraction": False,
        "vlm_enabled": False,
        "vlm_provider": "ollama",
        "vlm_api_key": "",
        "vlm_model": "qwen2-vl:2b",
        "vlm_endpoint": "http://localhost:11434",
        "vlm_prompt": "prompt",
        "vlm_max_concurrent": 1,
        "num_threads": 1,
        "cuda_use_flash_attention": False,
    }

    def fake_process_pdf(pdf_path, output_dir, options=None):
        md_file = output_dir / options.md_output_name
        md_file.write_text("# Mock Output", encoding="utf-8")
        return md_file

    with patch("docling_lib.converter.process_pdf", side_effect=fake_process_pdf):
        result = process_pdf_multi_process_worker(
            str(input_file),
            str(output_dir),
            options_dict,
        )
        assert result is not None
        assert Path(result).exists()
        assert (output_dir / "processed_document.md").exists()


def test_process_pdf_multi_process_worker_failure(tmp_path):
    """
    Verify process_pdf_multi_process_worker returns None when conversion fails.
    """
    input_file = tmp_path / "invalid.pdf"
    input_file.write_text("invalid content", encoding="utf-8")
    output_dir = tmp_path / "out"

    options_dict = {
        "image_dir_name": "images",
        "md_output_name": "processed_document.md",
        "image_scale": 2.0,
        "table_format": "html",
        "do_formula": False,
        "do_ocr": False,
        "do_chart": False,
        "do_code": False,
        "include_page_breaks": False,
        "include_kv_extraction": False,
        "vlm_enabled": False,
        "vlm_provider": "ollama",
        "vlm_api_key": "",
        "vlm_model": "qwen2-vl:2b",
        "vlm_endpoint": "http://localhost:11434",
        "vlm_prompt": "prompt",
        "vlm_max_concurrent": 1,
        "num_threads": 1,
        "cuda_use_flash_attention": False,
    }

    with patch("docling_lib.converter.process_pdf", return_value=None):
        result = process_pdf_multi_process_worker(
            str(input_file),
            str(output_dir),
            options_dict,
        )
        assert result is None
