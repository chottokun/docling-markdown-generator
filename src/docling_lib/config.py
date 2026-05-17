import logging
import os
from pathlib import Path

# --- Constants ---
MD_OUTPUT_NAME = "processed_document.md"
IMAGE_DIR_NAME = "images"
IMAGE_RESOLUTION_SCALE = 2.0  # Higher value for better image quality

# Directory configurations
UPLOAD_DIR = Path(os.getenv("DOCLING_UPLOAD_DIR", "uploads"))
OUTPUT_DIR = Path(os.getenv("DOCLING_OUTPUT_DIR", "output"))

# Security configurations
MAX_UPLOAD_SIZE = int(os.getenv("DOCLING_MAX_UPLOAD_SIZE", 20 * 1024 * 1024))  # Default 20MB
# Default to empty list for security (must be explicitly configured)
CORS_ORIGINS = [
    o.strip() for o in os.getenv("DOCLING_CORS_ORIGINS", "").split(",") if o.strip()
]

# API Key for authentication (Optional: if not set, authentication is disabled)
API_KEY = os.getenv("DOCLING_API_KEY")

# Rate limiting configurations
RATE_LIMIT_REQUESTS = int(os.getenv("DOCLING_RATE_LIMIT_REQUESTS", "5"))
RATE_LIMIT_WINDOW = int(os.getenv("DOCLING_RATE_LIMIT_WINDOW", "60"))

# Docling v2.x Pipeline options
DO_FORMULA = os.getenv("DOCLING_DO_FORMULA", "True").lower() == "true"
DO_OCR = os.getenv("DOCLING_DO_OCR", "True").lower() == "true"
DO_CHART = os.getenv("DOCLING_DO_CHART", "False").lower() == "true"
DO_CODE = os.getenv("DOCLING_DO_CODE", "False").lower() == "true"

def setup_logging():
    """Configures global logging for the library/CLI."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
