import logging
import os
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from .config import MAX_UPLOAD_SIZE, OUTPUT_DIR, UPLOAD_DIR, setup_logging
from .converter import process_pdf
from .utils import sanitize_log_message

# --- Logging Setup ---
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Docling Markdown Conversion Server")

# Ensure directories exist
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


def _validate_content_length(content_length: int | None):
    """Validate the Content-Length header against MAX_UPLOAD_SIZE."""
    if content_length and content_length > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Payload Too Large. Maximum size is {MAX_UPLOAD_SIZE} bytes.",
        )


def _validate_extension(filename: str) -> str:
    """Validate the file extension and return it if valid."""
    allowed_extensions = {".pdf", ".docx", ".pptx", ".xlsx"}
    file_ext = Path(filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Supported: {allowed_extensions}",
        )
    return file_ext


async def _save_upload_temp(file: UploadFile, suffix: str) -> Path:
    """
    Save the uploaded file to a temporary location with size validation.
    Reads in chunks to maintain memory efficiency and prevent DoS.
    """
    total_size = 0
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=suffix, dir=UPLOAD_DIR
    ) as tmp_file:
        # Re-read the upload stream in chunks to verify the actual size
        while True:
            chunk = await file.read(1024 * 1024)  # 1MB chunks
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_UPLOAD_SIZE:
                # Cleanup and raise error
                tmp_file.close()
                os.unlink(tmp_file.name)
                raise HTTPException(
                    status_code=413,
                    detail=f"Payload Too Large. Maximum size is {MAX_UPLOAD_SIZE} bytes.",
                )
            await run_in_threadpool(tmp_file.write, chunk)

        return Path(tmp_file.name)


async def _create_output_dir() -> tuple[str, Path]:
    """Create a unique output directory for the request and return its ID and path."""
    request_id = os.urandom(8).hex()
    request_output_dir = OUTPUT_DIR / request_id
    await run_in_threadpool(request_output_dir.mkdir, parents=True, exist_ok=True)
    return request_id, request_output_dir


async def _validate_and_format_response(
    result_path: Path | None, request_id: str
) -> dict[str, str]:
    """Validate result existence and format success response."""
    if not result_path or not await run_in_threadpool(result_path.exists):
        raise HTTPException(status_code=500, detail="Conversion failed.")

    return {
        "message": "Conversion successful",
        "markdown_file": result_path.name,
        "output_id": request_id,
        "download_url": f"/download/{request_id}/{result_path.name}",
    }


async def _cleanup_temp_file(tmp_path: Path | None):
    """Cleanup temporary input file."""
    if tmp_path and await run_in_threadpool(tmp_path.exists):
        await run_in_threadpool(tmp_path.unlink)


@app.post("/convert/")
async def convert_file(
    file: UploadFile = File(...), content_length: int | None = Header(None)
):
    """
    Endpoint to upload a document and convert it to Markdown.
    Includes validation for file size (via Content-Length header and read loop).
    """
    _validate_content_length(content_length)

    file_ext = _validate_extension(file.filename)
    tmp_path = None
    try:
        tmp_path = await _save_upload_temp(file, file_ext)
        request_id, request_output_dir = await _create_output_dir()

        sanitized_filename = sanitize_log_message(file.filename)
        logger.info(f"Processing file: {sanitized_filename}")

        # Use our process_pdf function wrapped in run_in_threadpool for concurrency.
        # It's now thread-safe due to the internal lock in converter.py.
        result_path = await run_in_threadpool(process_pdf, tmp_path, request_output_dir)

        return await _validate_and_format_response(result_path, request_id)

    except HTTPException:
        # Re-raise already formed HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"An error occurred during conversion: {e}")
        raise HTTPException(
            status_code=500, detail="An internal error occurred during conversion."
        ) from e
    finally:
        await _cleanup_temp_file(tmp_path)


@app.get("/download/{request_id}/{filename}")
async def download_file(request_id: str, filename: str):
    """
    Endpoint to download converted files.
    """

    def _get_safe_path():
        # Security: Prevent path traversal
        # Resolve to absolute paths and verify anchoring to OUTPUT_DIR
        resolved_output_dir = OUTPUT_DIR.resolve()
        safe_dir = (resolved_output_dir / request_id).resolve()
        file_path = (safe_dir / filename).resolve()
        return resolved_output_dir, safe_dir, file_path

    try:
        resolved_output_dir, safe_dir, file_path = await run_in_threadpool(
            _get_safe_path
        )

        # Check if the file is within its assigned request directory and OUTPUT_DIR
        in_output = file_path.is_relative_to(resolved_output_dir)
        in_safe = file_path.is_relative_to(safe_dir)
        if not in_output or not in_safe:
            logger.warning(f"Unauthorized download attempt: {request_id}/{filename}")
            raise HTTPException(status_code=404, detail="File not found.")

        if not await run_in_threadpool(file_path.exists) or not await run_in_threadpool(
            file_path.is_file
        ):
            raise HTTPException(status_code=404, detail="File not found.")

        return FileResponse(file_path)
    except (OSError, ValueError, HTTPException) as e:
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Error during file download path resolution: {e}")
        raise HTTPException(
            status_code=400, detail="Invalid request parameters."
        ) from e


@app.get("/")
async def root():
    return {"message": "Welcome to the Docling Markdown Conversion Server"}
