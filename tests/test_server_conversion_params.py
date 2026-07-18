from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import docling_lib.server
from docling_lib.server import app

client = TestClient(app)

TEST_DATA_DIR = Path("tests/test_data")
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)

DUMMY_DOCX = TEST_DATA_DIR / "test_document.docx"
if not DUMMY_DOCX.exists():
    DUMMY_DOCX.write_text("dummy docx content")


@patch("docling_lib.server.process_pdf")
def test_convert_file_with_parameters(mock_process, tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "output"
    upload_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(docling_lib.server, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(docling_lib.server, "OUTPUT_DIR", output_dir)

    # Let's mock process_pdf to inspect options passed to it
    options_passed = []

    def side_effect(input_path, request_output_dir, options=None):
        options_passed.append(options)
        res = request_output_dir / "processed_document.md"
        res.write_text("# Mocked Results")
        return res

    mock_process.side_effect = side_effect

    file_path = DUMMY_DOCX
    with open(file_path, "rb") as f:
        files = {
            "file": (
                file_path.name,
                f,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        # Pass custom form options to convert file
        data = {
            "table_format": "markdown",
            "include_page_breaks": "true",
            "include_kv_extraction": "true",
            "vlm_enabled": "true",
            "vlm_model": "custom-vlm-model",
            "vlm_endpoint": "http://ollama-custom:11434",
            "vlm_prompt": "カスタム説明してください",
            "num_threads": "8",
            "cuda_use_flash_attention": "true",
        }
        response = client.post("/convert/", files=files, data=data)

    assert response.status_code == 200
    res_data = response.json()
    assert res_data["message"] == "Conversion successful"

    # Assert option values were mapped correctly to process_pdf
    assert len(options_passed) == 1
    opts = options_passed[0]
    assert opts is not None
    assert opts.table_format == "markdown"
    assert opts.include_page_breaks is True
    assert opts.include_kv_extraction is True
    assert opts.vlm_enabled is True
    assert opts.vlm_model == "custom-vlm-model"
    assert opts.vlm_endpoint == "http://ollama-custom:11434"
    assert opts.vlm_prompt == "カスタム説明してください"
    assert opts.num_threads == 8
    assert opts.cuda_use_flash_attention is True
