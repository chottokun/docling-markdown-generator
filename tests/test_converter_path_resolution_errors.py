import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from docling_lib.converter import PDFConverter


def test_validate_and_resolve_paths_exception_handling(caplog):
    """
    Test that _validate_and_resolve_paths correctly logs and re-raises
    exceptions during path resolution.
    """
    converter = PDFConverter()
    output_dir = Path("/tmp/output")
    image_dir_name = "images"
    md_output_name = "output.md"

    # Mock Path.resolve to raise an Exception
    # We use a generic Exception as the goal is to test the 'except Exception' block
    with patch.object(Path, "resolve", side_effect=Exception("Simulated resolution error")):
        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception) as excinfo:
                converter._validate_and_resolve_paths(
                    output_dir=output_dir,
                    image_dir_name=image_dir_name,
                    md_output_name=md_output_name,
                )

    # Assertions
    assert "Simulated resolution error" in str(excinfo.value)
    assert "Security Error during path resolution" in caplog.text
    assert "Simulated resolution error" in caplog.text
