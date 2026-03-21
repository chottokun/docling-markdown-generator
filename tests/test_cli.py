from unittest.mock import patch

import pytest

from docling_lib.cli import entry_point, main

# --- Test Cases for main() ---


@patch("docling_lib.cli.process_pdf")
def test_main_happy_path(mock_process_pdf, tmp_path, pdf_downloader, monkeypatch):
    """
    Given: Valid CLI arguments.
    When: main() is called.
    Then: It should call the core process_pdf function with the correct arguments.
    """
    monkeypatch.chdir(tmp_path)
    pdf_path = pdf_downloader("https://arxiv.org/pdf/1706.03762.pdf")
    output_dir = tmp_path / "cli_output"
    mock_process_pdf.return_value = output_dir / "processed_document.md"  # Simulate success

    result = main([str(pdf_path), "--output-dir", str(output_dir)])

    assert result == 0
    mock_process_pdf.assert_called_once_with(
        pdf_path, output_dir, image_dir_name="images", md_output_name="processed_document.md", image_scale=2.0
    )


def test_main_missing_pdf_argument(capsys):
    """
    Given: CLI arguments without the required document file.
    When: main() is called.
    Then: It should exit with a status code 2.
    """
    with pytest.raises(SystemExit) as e:
        main([])
    assert e.value.code == 2
    captured = capsys.readouterr()
    assert "the following arguments are required: pdf_file" in captured.err


@patch("docling_lib.cli.process_pdf", return_value=None)
def test_main_processing_fails(
    mock_process_pdf, tmp_path, caplog, pdf_downloader, monkeypatch
):
    """
    Given: The core processing function fails (returns None).
    When: main() is called.
    Then: It should return an error code and log an error message.
    """
    monkeypatch.chdir(tmp_path)
    pdf_path = pdf_downloader("https://arxiv.org/pdf/1706.03762.pdf")
    result = main([str(pdf_path), "-o", str(tmp_path)])
    assert result == 1
    assert "Workflow failed" in caplog.text


@patch("docling_lib.cli.process_pdf")
def test_main_with_custom_image_dir(mock_process_pdf, tmp_path, pdf_downloader, monkeypatch):
    """
    Given: The --image-dir argument is provided.
    When: main() is called.
    Then: It should call process_pdf with the custom image directory name.
    """
    monkeypatch.chdir(tmp_path)
    pdf_path = pdf_downloader("https://arxiv.org/pdf/1706.03762.pdf")
    output_dir = tmp_path / "cli_output"
    custom_image_dir = "my_images"
    mock_process_pdf.return_value = output_dir / "processed.md"

    result = main(
        [
            str(pdf_path),
            "--output-dir",
            str(output_dir),
            "--image-dir",
            custom_image_dir,
        ]
    )

    assert result == 0
    mock_process_pdf.assert_called_once_with(
        pdf_path, output_dir, image_dir_name=custom_image_dir, md_output_name="processed_document.md", image_scale=2.0
    )


# --- Tests for entry_point() ---


@patch("docling_lib.cli.sys")
@patch("docling_lib.cli.main")
def test_entry_point_success(mock_main, mock_sys):
    mock_main.return_value = 0
    entry_point()
    mock_main.assert_called_once_with()
    mock_sys.exit.assert_called_once_with(0)


@patch("docling_lib.cli.sys")
@patch("docling_lib.cli.main", side_effect=SystemExit(2))
def test_entry_point_system_exit(mock_main, mock_sys):
    entry_point()
    mock_main.assert_called_once_with()
    mock_sys.exit.assert_called_once_with(2)

@patch("docling_lib.cli.logger")
@patch("docling_lib.cli.sys")
@patch("docling_lib.cli.main", side_effect=Exception("Test Error"))
def test_entry_point_unexpected_error(mock_main, mock_sys, mock_logger):
    entry_point()
    mock_main.assert_called_once_with()
    mock_logger.exception.assert_called_once()
    assert (
        "An unexpected error occurred in the CLI: Test Error"
        in mock_logger.exception.call_args[0][0]
    )
    mock_sys.exit.assert_called_once_with(1)
