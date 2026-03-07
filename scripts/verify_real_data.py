import logging
import sys
from pathlib import Path
from docling_lib.converter import process_pdf

# Configure logging to see the output
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def verify_all_samples():
    project_root = Path("/home/nobuhiko/project/Docling_pdf2markdown")
    test_data_dir = project_root / "tests" / "test_data"
    output_base_dir = project_root / "test_output_verification"
    output_base_dir.mkdir(parents=True, exist_ok=True)

    supported_extensions = [".pdf", ".docx", ".pptx", ".xlsx"]
    
    # Identify files to test
    test_files = [f for f in test_data_dir.iterdir() if f.suffix in supported_extensions]
    
    if not test_files:
        logger.error(f"No test files found in {test_data_dir}")
        return False

    success_count = 0
    failure_count = 0

    logger.info(f"Starting verification for {len(test_files)} files...")

    for test_file in test_files:
        logger.info(f"--- Processing: {test_file.name} ---")
        output_dir = output_base_dir / test_file.stem
        
        try:
            result_path = process_pdf(test_file, output_dir)
            
            if result_path and result_path.exists():
                logger.info(f"SUCCESS: Generated {result_path.relative_to(project_root)}")
                # Check for images dir
                images_dir = output_dir / "images"
                if images_dir.exists():
                    image_count = len(list(images_dir.glob("*.png")))
                    logger.info(f"         Found {image_count} images in {images_dir.relative_to(project_root)}")
                success_count += 1
            else:
                logger.error(f"FAILURE: Failed to process {test_file.name}")
                failure_count += 1
        except Exception as e:
            logger.exception(f"ERROR: Exception during processing of {test_file.name}: {e}")
            failure_count += 1

    logger.info("========================================")
    logger.info("Verification Summary:")
    logger.info(f"  Total Files: {len(test_files)}")
    logger.info(f"  Success:     {success_count}")
    logger.info(f"  Failure:     {failure_count}")
    logger.info("========================================")

    return failure_count == 0

if __name__ == "__main__":
    if verify_all_samples():
        sys.exit(0)
    else:
        sys.exit(1)
