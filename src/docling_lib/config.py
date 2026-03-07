import logging

# --- Constants ---
MD_OUTPUT_NAME = "processed_document.md"
IMAGE_DIR_NAME = "images"
IMAGE_RESOLUTION_SCALE = 2.0  # Higher value for better image quality

def setup_logging():
    """Configures global logging for the library/CLI."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
