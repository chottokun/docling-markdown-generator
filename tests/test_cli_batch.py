import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.mock_docling import mock_docling

# Call mock_docling before importing cli to mock docling dependencies
mock_docling()

from docling_lib.cli import main
from docling_lib.converter import (
    get_process_pool,
    process_pdf_multi_process_worker_with_timeout,
    shutdown_process_pool,
)


@pytest.fixture(autouse=True)
def clean_process_pool():
    shutdown_process_pool()
    yield
    shutdown_process_pool()


class MockPool:
    def submit(self, fn, *args, **kwargs):
        from concurrent.futures import Future
        fut = Future()
        try:
            res = fn(*args, **kwargs)
            fut.set_result(res)
        except Exception as e:
            fut.set_exception(e)
        return fut


def test_cli_batch_flat_directory(tmp_path, caplog, monkeypatch):
    """
    Given: A directory with multiple valid and invalid files.
    When: Running the CLI main in batch mode (non-recursive).
    Then: It should scan only the flat directory and process supported formats.
    """
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    # Supported files
    file1 = input_dir / "doc1.pdf"
    file1.write_text("%PDF-1.4 dummy", encoding="utf-8")
    file2 = input_dir / "doc2.docx"
    file2.write_text("docx dummy", encoding="utf-8")

    # Unsupported file
    file3 = input_dir / "doc3.txt"
    file3.write_text("text dummy", encoding="utf-8")

    # Nested file (should be ignored since recursive is False)
    nested_dir = input_dir / "nested"
    nested_dir.mkdir()
    file4 = nested_dir / "doc4.pdf"
    file4.write_text("%PDF-1.4 nested dummy", encoding="utf-8")

    output_dir = tmp_path / "output"

    def mock_worker(pdf_path, output_dir, options_dict):
        out_path = Path(output_dir) / "processed_document.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("# Processed", encoding="utf-8")
        return str(out_path)

    mock_pool = MockPool()

    with (
        patch("docling_lib.converter.get_process_pool", return_value=mock_pool),
        patch("docling_lib.converter.process_pdf_multi_process_worker", side_effect=mock_worker) as mock_run,
    ):
        result = main([str(input_dir), "--output-dir", str(output_dir)])

        assert result == 0
        # Only the flat supported files should be processed
        assert mock_run.call_count == 2

        called_paths = [Path(call[0][0]) for call in mock_run.call_args_list]
        assert file1 in called_paths
        assert file2 in called_paths
        assert file4 not in called_paths


def test_cli_batch_recursive_directory(tmp_path, monkeypatch):
    """
    Given: A nested directory structure.
    When: Running the CLI main in recursive batch mode.
    Then: It should find files in nested directories and preserve/mirror output structures.
    """
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    # Root level file
    file1 = input_dir / "doc1.pdf"
    file1.write_text("%PDF-1.4 dummy", encoding="utf-8")

    # Nested level file
    nested_dir = input_dir / "nested"
    nested_dir.mkdir()
    file2 = nested_dir / "doc2.docx"
    file2.write_text("docx dummy", encoding="utf-8")

    output_dir = tmp_path / "output"

    def mock_worker(pdf_path, output_dir, options_dict):
        out_path = Path(output_dir) / "processed_document.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("# Processed", encoding="utf-8")
        return str(out_path)

    mock_pool = MockPool()

    with (
        patch("docling_lib.converter.get_process_pool", return_value=mock_pool),
        patch("docling_lib.converter.process_pdf_multi_process_worker", side_effect=mock_worker) as mock_run,
    ):
        result = main([str(input_dir), "--output-dir", str(output_dir), "--recursive"])

        assert result == 0
        assert mock_run.call_count == 2

        called_args = mock_run.call_args_list
        # Output paths should preserve the directory structure
        out_paths = [Path(arg[0][1]) for arg in called_args]

        expected_out1 = output_dir / "doc1"
        expected_out2 = output_dir / "nested" / "doc2"

        assert expected_out1 in out_paths
        assert expected_out2 in out_paths


def test_task_timeout_handling(tmp_path):
    """
    Given: A task that times out during multi-process execution.
    When: It is submitted with a timeout option.
    Then: It should abort the task gracefully, log error, and force-recreate the pool.
    """
    input_file = tmp_path / "doc.pdf"
    input_file.write_text("%PDF-1.4", encoding="utf-8")
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

    # Simulate a hanging task using a mock pool future that raises TimeoutError
    mock_future = MagicMock()
    mock_future.result.side_effect = TimeoutError()

    mock_pool = MagicMock()
    mock_pool.submit.return_value = mock_future

    with (
        patch("docling_lib.converter.get_process_pool") as mock_get_pool,
        patch("docling_lib.converter.logger") as mock_logger,
    ):
        mock_get_pool.return_value = mock_pool

        res = process_pdf_multi_process_worker_with_timeout(
            str(input_file),
            str(output_dir),
            options_dict,
            timeout=0.01,
        )

        assert res is None
        # Should call cancel on the hanging task's future
        mock_future.cancel.assert_called_once()
        # Should force recreate the process pool to dispose of the hung worker
        mock_get_pool.assert_any_call(force_recreate=True)
        # Should log the timeout error
        mock_logger.error.assert_any_call(
            f"Task processing timed out for file: {input_file} (timeout=0.01s)"
        )


def test_process_pool_recycling(tmp_path):
    """
    Given: The maximum tasks per child limit is reached.
    When: Requesting a process pool for a new task.
    Then: The old process pool should be cleanly shutdown and recycled.
    """
    from docling_lib.config import DOCLING_MAX_TASKS_PER_CHILD

    # Retrieve first pool
    pool1 = get_process_pool()
    assert pool1 is not None

    # Submit tasks to hit the recycle limit
    from docling_lib.converter import increment_submitted_tasks
    for _ in range(DOCLING_MAX_TASKS_PER_CHILD + 1):
        increment_submitted_tasks()

    # Retrieving next pool should trigger a recycle
    pool2 = get_process_pool()
    assert pool2 is not pool1  # A new pool must have been created


def test_batch_parallel_concurrency(tmp_path):
    """
    Given: A list of multiple documents for batch conversion.
    When: Running the CLI main.
    Then: Tasks should be submitted concurrently up to DOCLING_MAX_WORKERS.
    """
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    for i in range(4):
        (input_dir / f"doc_{i}.pdf").write_text("%PDF-1.4 dummy", encoding="utf-8")

    output_dir = tmp_path / "output"

    mock_pool = MagicMock()
    mock_futures = [MagicMock() for _ in range(4)]

    # Simple mock where done() initially returns False then True
    done_states = {f: [False, False, True] for f in mock_futures}

    for f in mock_futures:
        def make_done_mock(fut):
            def side_effect():
                states = done_states[fut]
                if len(states) > 1:
                    return states.pop(0)
                return states[0]
            return side_effect
        f.done.side_effect = make_done_mock(f)
        f.result.return_value = "processed"

    mock_pool.submit.side_effect = mock_futures

    with (
        patch("docling_lib.converter.get_process_pool", return_value=mock_pool),
        patch("docling_lib.config.DOCLING_MAX_WORKERS", 2),
    ):
        result = main([str(input_dir), "--output-dir", str(output_dir)])
        assert result == 0
        assert mock_pool.submit.call_count == 4


def test_batch_ram_monitoring_pause(tmp_path):
    """
    Given: RAM utilization exceeds 85%.
    When: Running the CLI batch conversion.
    Then: Submission of new tasks must be paused until RAM utilization drops.
    """
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "doc.pdf").write_text("%PDF-1.4 dummy", encoding="utf-8")

    output_dir = tmp_path / "output"

    mock_mem_high = MagicMock()
    mock_mem_high.percent = 90.0

    mock_mem_low = MagicMock()
    mock_mem_low.percent = 50.0

    # Return high memory twice, then low memory
    virtual_memory_side_effects = [mock_mem_high, mock_mem_high, mock_mem_low]

    mock_pool = MagicMock()
    mock_future = MagicMock()
    mock_future.done.return_value = True
    mock_future.result.return_value = "processed"
    mock_pool.submit.return_value = mock_future

    with (
        patch("psutil.virtual_memory", side_effect=virtual_memory_side_effects),
        patch("docling_lib.converter.get_process_pool", return_value=mock_pool),
        patch("docling_lib.config.DOCLING_MAX_WORKERS", 2),
    ):
        result = main([str(input_dir), "--output-dir", str(output_dir)])
        assert result == 0
        assert mock_pool.submit.call_count == 1


def test_batch_single_task_timeout_isolation(tmp_path):
    """
    Given: Two concurrent tasks in batch conversion.
    When: One task times out while the other completes successfully.
    Then: The timed-out task is handled without interrupting the successful task.
    """
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    file1 = input_dir / "doc1.pdf"
    file1.write_text("%PDF-1.4 dummy", encoding="utf-8")
    file2 = input_dir / "doc2.docx"
    file2.write_text("docx dummy", encoding="utf-8")

    output_dir = tmp_path / "output"

    mock_pool = MagicMock()

    # Task 1 (doc1.pdf) times out; Task 2 (doc2.docx) succeeds.
    future1 = MagicMock()
    future1.done.return_value = False

    future2 = MagicMock()
    future2.done.return_value = True
    future2.result.return_value = "processed"

    # Simple done() mocker that lets the loop terminate
    done_states = {
        future1: [False, False, True], # Timeout checked via elapsed time
    }

    def make_done_mock(fut):
        def side_effect():
            if fut == future2:
                return True
            states = done_states[fut]
            if len(states) > 1:
                return states.pop(0)
            return states[0]
        return side_effect

    future1.done.side_effect = make_done_mock(future1)

    mock_pool.submit.side_effect = [future1, future2]

    with (
        patch("docling_lib.converter.get_process_pool", return_value=mock_pool) as mock_get_pool,
        patch("docling_lib.config.DOCLING_MAX_WORKERS", 2),
    ):
        result = main([str(input_dir), "--output-dir", str(output_dir), "--timeout", "0.05"])
        # One success and one failure -> result should be 1
        assert result == 1
        assert mock_pool.submit.call_count == 2
        future1.cancel.assert_called_once()
