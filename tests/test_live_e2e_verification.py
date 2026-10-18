import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from docling_lib.converter import DocumentConversionOptions, process_pdf
from docling_lib.server import app


def test_e2e_real_pdf_conversion():
    """Real end-to-end PDF conversion without mocks using sample1_simple.pdf."""
    sample_pdf = Path("tests/data/real_world/sample1_simple.pdf")
    assert sample_pdf.exists(), "Sample PDF must exist for real test"

    output_dir = Path("test_e2e_cli_output")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        options = DocumentConversionOptions(
            image_dir_name="images",
            md_output_name="output.md",
            table_format="markdown",
            do_ocr=False,  # faster run
        )

        res_path = process_pdf(
            pdf_path=sample_pdf,
            output_dir=output_dir,
            options=options,
        )

        assert res_path is not None
        assert res_path.exists()
        content = res_path.read_text(encoding="utf-8")
        assert "Dummy PDF file" in content
        assert (output_dir / "images").exists()
    finally:
        if output_dir.exists():
            shutil.rmtree(output_dir)


def test_e2e_real_pdf_with_serializer_cache():
    """Real end-to-end conversion of multi-element document (sample5_brochure.pdf) to test serializer caching."""
    sample_pdf = Path("tests/data/real_world/sample5_brochure.pdf")
    assert sample_pdf.exists(), "Sample brochure PDF must exist"

    output_dir = Path("test_e2e_brochure_output")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        options = DocumentConversionOptions(
            image_dir_name="images",
            md_output_name="brochure.md",
            table_format="html",
            do_ocr=False,
        )

        res_path = process_pdf(
            pdf_path=sample_pdf,
            output_dir=output_dir,
            options=options,
        )

        assert res_path is not None
        assert res_path.exists()
        content = res_path.read_text(encoding="utf-8")
        assert len(content) > 0
        assert (output_dir / "images").exists()
    finally:
        if output_dir.exists():
            shutil.rmtree(output_dir)


def test_e2e_server_real_conversion_and_metrics(monkeypatch):
    """End-to-end FastAPI test: /convert endpoint and /metrics endpoint without mocks."""
    sample_pdf = Path("tests/data/real_world/sample1_simple.pdf")
    assert sample_pdf.exists()

    work_dir = Path("test_e2e_server_workdir")
    if work_dir.exists():
        shutil.rmtree(work_dir)
    upload_dir = work_dir / "uploads"
    output_dir = work_dir / "output"
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DOCLING_ALLOW_ABSOLUTE_OUTPUT_DIR", "true")

    import docling_lib.server
    monkeypatch.setattr(docling_lib.server, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(docling_lib.server, "OUTPUT_DIR", output_dir)

    try:
        client = TestClient(app)

        # 1. Check root welcome endpoint
        root_res = client.get("/")
        assert root_res.status_code == 200
        assert "Welcome" in root_res.json()["message"]

        # 2. Check metrics endpoint (refactored Prometheus text generation in PR #237)
        metrics_before = client.get("/metrics")
        assert metrics_before.status_code == 200
        assert "docling_conversions_total" in metrics_before.text
        assert "docling_memory_used_bytes" in metrics_before.text

        # 3. Post real PDF to /convert/ (triggers _build_options_dict -> to_dict() and multiprocess worker -> from_dict())
        with open(sample_pdf, "rb") as f:
            response = client.post(
                "/convert/",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"table_format": "markdown"},
            )

        assert response.status_code == 200, f"Conversion failed: {response.text}"
        data = response.json()
        assert data["message"] == "Conversion successful"
        assert "download_url" in data
        assert "output_id" in data

        # 4. Download converted file to verify content
        download_res = client.get(data["download_url"])
        assert download_res.status_code == 200
        assert "Dummy PDF file" in download_res.text

        # 5. Check metrics updated after conversion
        metrics_after = client.get("/metrics")
        assert metrics_after.status_code == 200
        assert 'docling_conversions_total{status="success"}' in metrics_after.text
    finally:
        if work_dir.exists():
            shutil.rmtree(work_dir)


def test_adversarial_options_injection_and_backward_compatibility():
    """Adversarial testing: passing unrecognized fields, empty strings, and type coercion."""
    malicious_or_corrupt_data = {
        "image_dir_name": "safe_dir",
        "unknown_extra_injection": "'; DROP TABLE options; --",
        "artifacts_path": "",
        "nested_unsupported": {"key": "val"},
        "do_ocr": True,
        "table_format": "html",
    }

    # Verify options deserialization ignores unauthorized or unknown fields safely
    options = DocumentConversionOptions.from_dict(malicious_or_corrupt_data)
    assert options.image_dir_name == "safe_dir"
    assert options.artifacts_path is None
    assert not hasattr(options, "unknown_extra_injection")
    assert not hasattr(options, "nested_unsupported")

    # Verify to_dict serializes safely
    d = options.to_dict()
    assert "unknown_extra_injection" not in d
    assert d["artifacts_path"] is None
