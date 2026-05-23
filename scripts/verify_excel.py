import os
import sys
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Ensure src is in python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from docling_lib.converter import process_pdf, DocumentConversionOptions

def main():
    project_root = Path(__file__).resolve().parent.parent
    xlsx_path = project_root / "tests" / "data" / "real_world" / "gijutsu_matrix_20260214.xlsx"
    output_dir = project_root / "output" / "gijutsu_matrix"
    
    logger.info(f"Checking if target file exists at: {xlsx_path}")
    if not xlsx_path.exists():
        logger.error(f"File not found: {xlsx_path}")
        # Check files in real_world directory
        real_world_dir = project_root / "tests" / "data" / "real_world"
        if real_world_dir.exists():
            logger.info("Files in tests/data/real_world:")
            for f in real_world_dir.iterdir():
                logger.info(f"  {f.name}")
        sys.exit(1)
        
    logger.info(f"Starting conversion for: {xlsx_path}")
    logger.info(f"Output directory: {output_dir}")
    
    options = DocumentConversionOptions(
        table_format="html",
        do_ocr=False  # speed up if needed, or leave default
    )
    
    try:
        # docling requires output_dir path traversal checks.
        # Since we use process_pdf, it resolves path relative to current working directory.
        # Let's ensure output_dir is within allowed workspace
        os.makedirs(output_dir, exist_ok=True)
        
        # We need to change cwd to project root so path verification passes
        os.chdir(project_root)
        
        # output_dir relative to project_root
        relative_output_dir = Path("output") / "gijutsu_matrix"
        
        result_path = process_pdf(xlsx_path, relative_output_dir, options=options)
        
        if result_path and result_path.exists():
            logger.info("Conversion succeeded!")
            logger.info(f"Result file: {result_path}")
            
            # Print first 20 lines of markdown to verify the structure
            content = result_path.read_text(encoding="utf-8")
            logger.info("--- First 50 lines of generated Markdown ---")
            lines = content.splitlines()
            for line in lines[:50]:
                print(line)
            logger.info("--- End of preview ---")
            
            # Print table extraction feedback
            if "<table>" in content:
                logger.info("High-fidelity HTML table structures were found in the output!")
            else:
                logger.info("No HTML tables found. Standard markdown table or plain text might be used.")
                
        else:
            logger.error("Conversion failed. process_pdf returned None or file does not exist.")
            sys.exit(1)
            
    except Exception as e:
        logger.exception(f"Unexpected error during verification: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
