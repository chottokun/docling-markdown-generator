import logging
import os
from pathlib import Path

# --- Constants ---
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".html",
    ".htm",
    ".md",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".xbrl",
    ".eml",
    ".msg",
    ".epub",
    ".tex",
    ".vtt",
}
MD_OUTPUT_NAME = "processed_document.md"
IMAGE_DIR_NAME = "images"
IMAGE_RESOLUTION_SCALE = 2.0  # Higher value for better image quality

# Directory configurations
UPLOAD_DIR = Path(os.getenv("DOCLING_UPLOAD_DIR", "uploads"))
OUTPUT_DIR = Path(os.getenv("DOCLING_OUTPUT_DIR", "output"))

# Security configurations
MAX_UPLOAD_SIZE = int(
    os.getenv("DOCLING_MAX_UPLOAD_SIZE", 20 * 1024 * 1024)
)  # Default 20MB
# Default to empty set for security (must be explicitly configured)
CORS_ORIGINS = set(
    o.strip() for o in os.getenv("DOCLING_CORS_ORIGINS", "").split(",") if o.strip()
)

# API Key for authentication (Optional: if not set, authentication is disabled)
API_KEY = os.getenv("DOCLING_API_KEY")

# Rate limiting configurations
RATE_LIMIT_REQUESTS = int(os.getenv("DOCLING_RATE_LIMIT_REQUESTS", "5"))
RATE_LIMIT_WINDOW = int(os.getenv("DOCLING_RATE_LIMIT_WINDOW", "60"))
# Trusted proxies list for rate limiting IP headers (e.g. "127.0.0.1, 10.0.0.0/8, *")
TRUSTED_PROXIES = [
    p.strip() for p in os.getenv("DOCLING_TRUSTED_PROXIES", "").split(",") if p.strip()
]

# Docling v2.x Pipeline options
DO_FORMULA = os.getenv("DOCLING_DO_FORMULA", "True").lower() == "true"
DO_OCR = os.getenv("DOCLING_DO_OCR", "True").lower() == "true"
DO_CHART = os.getenv("DOCLING_DO_CHART", "False").lower() == "true"
DO_CODE = os.getenv("DOCLING_DO_CODE", "False").lower() == "true"
USE_GPU = os.getenv("DOCLING_USE_GPU", "True").lower() == "true"
DOCLING_NUM_THREADS = int(os.getenv("DOCLING_NUM_THREADS", "4"))
DOCLING_CUDA_FLASH_ATTENTION = (
    os.getenv("DOCLING_CUDA_FLASH_ATTENTION", "False").lower() == "true"
)

# New configurations for Ollama, Page Break and Table format
DOCLING_TABLE_FORMAT = os.getenv("DOCLING_TABLE_FORMAT", "html")
DOCLING_VLM_ENABLED = os.getenv("DOCLING_VLM_ENABLED", "False").lower() == "true"
DOCLING_VLM_PROVIDER = os.getenv("DOCLING_VLM_PROVIDER", "ollama")
DOCLING_VLM_API_KEY = os.getenv("DOCLING_VLM_API_KEY", "")
DOCLING_VLM_MODEL = os.getenv("DOCLING_VLM_MODEL", "qwen2-vl:2b")
DOCLING_VLM_ENDPOINT = os.getenv("DOCLING_VLM_ENDPOINT", "http://localhost:11434")
DOCLING_VLM_PROMPT = os.getenv(
    "DOCLING_VLM_PROMPT", "この画像の詳細な説明文を日本語で作成してください。"
)
DOCLING_VLM_MAX_CONCURRENT = int(os.getenv("DOCLING_VLM_MAX_CONCURRENT", "5"))
DOCLING_INCLUDE_PAGE_BREAKS = (
    os.getenv("DOCLING_INCLUDE_PAGE_BREAKS", "False").lower() == "true"
)
DOCLING_INCLUDE_KV_EXTRACTION = (
    os.getenv("DOCLING_INCLUDE_KV_EXTRACTION", "False").lower() == "true"
)

def setup_logging():
    """Configures global logging for the library/CLI."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
