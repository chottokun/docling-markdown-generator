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
from .converter import DocumentConversionOptions, process_pdf

# Configure logging for the CLI tool
logger = logging.getLogger(__name__)
setup_logging()


from .config import ALLOWED_EXTENSIONS

def setup_parser():
    """Sets up and returns the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="Extract markdown, figures, and tables from documents (PDF, DOCX, PPTX, XLSX, HTML, XBRL, Email, etc.) with high accuracy."
    )
    parser.add_argument(
        "pdf_file",
        type=Path,
        help="Path to the input document file or directory (PDF, DOCX, PPTX, XLSX, HTML, XBRL, Email, EPUB, LaTeX, WebVTT).",
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
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively scan the input directory for documents.",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=None,
        help="Task level timeout in seconds for processing each file.",
    )
    return parser


def main(args=None):
    """
    Main function for the command-line interface.
    Parses arguments and runs the high-accuracy document processing workflow.
    """
    parser = setup_parser()
    parsed_args = parser.parse_args(args if args is not None else sys.argv[1:])

    input_path = parsed_args.pdf_file

    options = DocumentConversionOptions(
        image_dir_name=parsed_args.image_dir,
        md_output_name=parsed_args.output_name,
        image_scale=parsed_args.image_scale,
    )

    if input_path.is_dir():
        # Batch conversion mode
        logger.info(f"Starting batch workflow for directory: {input_path}")

        # Scan for files with allowed extensions
        if parsed_args.recursive:
            file_generator = input_path.rglob("*")
        else:
            file_generator = input_path.glob("*")

        files_to_convert = [
            f for f in file_generator
            if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS
        ]

        if not files_to_convert:
            logger.warning(f"No supported files found in directory {input_path}")
            return 0

        logger.info(f"Found {len(files_to_convert)} files to convert.")

        import psutil
        import time
        from .converter import (
            get_process_pool,
            process_pdf_multi_process_worker,
            increment_submitted_tasks,
            get_active_tasks_count,
            increment_active_tasks,
            decrement_active_tasks,
        )
        from .config import DOCLING_MAX_WORKERS

        success_count = 0
        failure_count = 0

        pending_files = list(files_to_convert)
        active_futures = {}  # future -> (file_path, start_time, file_output_dir)

        timeout = parsed_args.timeout
        ram_warning_logged = False

        while pending_files or active_futures:
            # 1. Reap completed and timed out futures
            done_futures = []
            timeout_occurred = False
            for future in list(active_futures.keys()):
                file_path, start_time, file_output_dir = active_futures[future]

                if future.done():
                    done_futures.append(future)
                    try:
                        result_str = future.result()
                        if result_str:
                            logger.info(f"Successfully processed batch file: {file_path}")
                            success_count += 1
                        else:
                            logger.error(f"Failed to process batch file: {file_path}")
                            failure_count += 1
                    except Exception as e:
                        logger.error(f"Exception during processing of batch file {file_path}: {e}")
                        failure_count += 1
                    finally:
                        decrement_active_tasks()
                elif timeout is not None and (time.time() - start_time) > timeout:
                    done_futures.append(future)
                    logger.error(f"Task processing timed out for file: {file_path} (timeout={timeout}s)")
                    future.cancel()
                    failure_count += 1
                    decrement_active_tasks()
                    timeout_occurred = True

            # Remove completed/canceled futures from the map
            for future in done_futures:
                active_futures.pop(future, None)

            if timeout_occurred:
                # Cancel all other currently running futures and put their files back into pending_files queue
                for fut, (f_path, _, _) in list(active_futures.items()):
                    fut.cancel()
                    decrement_active_tasks()
                    pending_files.insert(0, f_path)
                active_futures.clear()

                # Force recreate the pool to terminate hung processes immediately using OS-level process terminate
                logger.warning("Forcing pool recreation due to task timeout...")
                get_process_pool(force_recreate=True)

            # 2. Check if we need to drain and recycle due to task limit
            from .converter import get_tasks_submitted_count
            from .config import DOCLING_MAX_TASKS_PER_CHILD
            if get_tasks_submitted_count() >= DOCLING_MAX_TASKS_PER_CHILD:
                if active_futures:
                    # Let existing tasks drain before recycling
                    if pending_files or active_futures:
                        time.sleep(0.1)
                    continue
                else:
                    # All active tasks are drained, recycle the pool now
                    logger.info("Drained all active tasks. Recycling process pool due to tasks threshold...")
                    get_process_pool(force_recreate=True)

            # 3. Submit new tasks concurrently if limit and RAM constraints allow
            paused_by_ram = False
            while pending_files and len(active_futures) < DOCLING_MAX_WORKERS:
                # Dynamic host RAM monitoring using psutil
                mem = psutil.virtual_memory()
                if mem.percent > 85.0:
                    if not ram_warning_logged:
                        logger.warning(
                            f"System memory usage is too high ({mem.percent}%). "
                            "Pausing submission of new batch tasks..."
                        )
                        ram_warning_logged = True
                    paused_by_ram = True
                    break
                else:
                    ram_warning_logged = False

                file_path = pending_files.pop(0)

                # Recreate output structure to mirror input folder layout if recursive is set
                if parsed_args.recursive:
                    relative_path = file_path.relative_to(input_path).parent
                    file_output_dir = parsed_args.output_dir / relative_path / file_path.stem
                else:
                    file_output_dir = parsed_args.output_dir / file_path.stem

                logger.info(f"Processing batch file concurrently: {file_path} -> {file_output_dir}")

                options_dict = {
                    "image_dir_name": options.image_dir_name,
                    "md_output_name": options.md_output_name,
                    "image_scale": options.image_scale,
                    "table_format": options.table_format,
                    "do_formula": options.do_formula,
                    "do_ocr": options.do_ocr,
                    "do_chart": options.do_chart,
                    "do_code": options.do_code,
                    "include_page_breaks": options.include_page_breaks,
                    "include_kv_extraction": options.include_kv_extraction,
                    "vlm_enabled": options.vlm_enabled,
                    "vlm_provider": options.vlm_provider,
                    "vlm_api_key": options.vlm_api_key,
                    "vlm_model": options.vlm_model,
                    "vlm_endpoint": options.vlm_endpoint,
                    "vlm_prompt": options.vlm_prompt,
                    "vlm_max_concurrent": options.vlm_max_concurrent,
                    "num_threads": options.num_threads,
                    "cuda_use_flash_attention": options.cuda_use_flash_attention,
                }

                # Get the process pool (will automatically recycle if DOCLING_MAX_TASKS_PER_CHILD is hit)
                pool = get_process_pool()
                increment_submitted_tasks()
                increment_active_tasks()

                future = pool.submit(
                    process_pdf_multi_process_worker,
                    str(file_path),
                    str(file_output_dir),
                    options_dict,
                )
                active_futures[future] = (file_path, time.time(), file_output_dir)

            if pending_files or active_futures:
                if paused_by_ram and not active_futures:
                    time.sleep(2.0)
                else:
                    time.sleep(0.1)

        logger.info(f"Batch conversion completed. Successes: {success_count}, Failures: {failure_count}")
        return 0 if failure_count == 0 else 1

    else:
        # Single file conversion mode
        logger.info(f"Starting single-file workflow for: {input_path}")
        result_path = process_pdf(
            input_path,
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
