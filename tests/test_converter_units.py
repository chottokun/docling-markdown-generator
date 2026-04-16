import logging
from pathlib import Path
from docling_lib.converter import _validate_input_path

def test_validate_input_path_exists(tmp_path):
    """Test that _validate_input_path returns True when the file exists."""
    # Setup: Create a dummy file
    test_file = tmp_path / "test.pdf"
    test_file.touch()

    # Act
    result = _validate_input_path(test_file)

    # Assert
    assert result is True

def test_validate_input_path_not_exists(tmp_path, caplog):
    """Test that _validate_input_path returns False and logs an error when the file does not exist."""
    # Setup: Path to a non-existent file
    test_file = tmp_path / "non_existent.pdf"

    # Act
    with caplog.at_level(logging.ERROR):
        result = _validate_input_path(test_file)

    # Assert
    assert result is False
    assert f"Input file not found: {test_file}" in caplog.text
