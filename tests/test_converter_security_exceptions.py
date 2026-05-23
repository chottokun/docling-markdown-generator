import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from docling_lib.converter import PDFConverter, _validate_output_security


def test_validate_output_security_exception(caplog):
    """
    Verify that _validate_output_security handles exceptions during path resolution
    by logging an error and returning False.
    """
    with patch("docling_lib.converter.Path.cwd", side_effect=RuntimeError("CWD failure")):
        with caplog.at_level(logging.ERROR):
            result = _validate_output_security(Path("output"))
            assert result is False
            assert "Security Error during path resolution: CWD failure" in caplog.text


def test_validate_and_resolve_paths_exception(caplog):
    """
    Verify that PDFConverter._validate_and_resolve_paths handles exceptions
    during path resolution by logging an error and re-raising the exception.
    """
    converter = PDFConverter()
    # Mocking Path.resolve on the Path class used within the module
    with patch("docling_lib.converter.Path.resolve", side_effect=RuntimeError("Resolve failure")):
        with caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError, match="Resolve failure"):
                converter._validate_and_resolve_paths(
                    output_dir=Path("out"),
                    image_dir_name="images",
                    md_output_name="output.md"
                )
            assert "Security Error during path resolution: Resolve failure" in caplog.text
