from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from pathlib import Path
import shutil
import tempfile
import logging
import os

from .converter import process_pdf
from .config import setup_logging, UPLOAD_DIR, OUTPUT_DIR
from .utils import sanitize_log_message

# --- Logging Setup ---
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Docling Markdown Conversion Server")

# Ensure directories exist
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


@app.post("/convert/")
async def convert_file(file: UploadFile = File(...)):
    """
    Endpoint to upload a document and convert it to Markdown.
    """
    # Security: Validate file extension
    allowed_extensions = {".pdf", ".docx", ".pptx", ".xlsx"}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Supported: {allowed_extensions}",
        )

    # Save uploaded file temporarily
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=file_ext, dir=UPLOAD_DIR
        ) as tmp_file:
            await run_in_threadpool(shutil.copyfileobj, file.file, tmp_file)
            tmp_path = Path(tmp_file.name)

        # Create a unique output directory for this request
        request_id = os.urandom(8).hex()
        request_output_dir = OUTPUT_DIR / request_id
        request_output_dir.mkdir(parents=True, exist_ok=True)

        sanitized_filename = sanitize_log_message(file.filename)
        logger.info(f"Processing file: {sanitized_filename}")
        
        # Use our process_pdf function wrapped in run_in_threadpool for concurrency.
        # It's now thread-safe due to the internal lock in converter.py.
        result_path = await run_in_threadpool(process_pdf, tmp_path, request_output_dir)

        if not result_path or not result_path.exists():
            raise HTTPException(status_code=500, detail="Conversion failed.")

        # For simplicity, we return the main markdown file.
        # Images are saved in request_output_dir/images
        return {
            "message": "Conversion successful",
            "markdown_file": result_path.name,
            "output_id": request_id,
            "download_url": f"/download/{request_id}/{result_path.name}",
        }

    except HTTPException:
        # Re-raise already formed HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"An error occurred during conversion: {e}")
        raise HTTPException(
            status_code=500, detail="An internal error occurred during conversion."
        )
    finally:
        # Cleanup temporary input file
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


@app.get("/download/{request_id}/{filename}")
async def download_file(request_id: str, filename: str):
    """
    Endpoint to download converted files.
    """
    try:
        # Security: Prevent path traversal
        # Resolve to absolute paths and verify anchoring to OUTPUT_DIR
        resolved_output_dir = OUTPUT_DIR.resolve()
        safe_dir = (resolved_output_dir / request_id).resolve()
        file_path = (safe_dir / filename).resolve()

        # Check if the file is within its assigned request directory and OUTPUT_DIR
        if not file_path.is_relative_to(resolved_output_dir) or not file_path.is_relative_to(safe_dir):
            logger.warning(f"Unauthorized download attempt: {request_id}/{filename}")
            raise HTTPException(status_code=404, detail="File not found.")

        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="File not found.")

        return FileResponse(file_path)
    except (OSError, ValueError, HTTPException) as e:
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Error during file download path resolution: {e}")
        raise HTTPException(status_code=400, detail="Invalid request parameters.")


@app.get("/")
async def root():
    return {"message": "Welcome to the Docling Markdown Conversion Server"}
