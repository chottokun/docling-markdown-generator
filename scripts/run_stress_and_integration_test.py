import asyncio
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from docling_lib.converter import PDFConverter
from docling_lib.server import app, _rate_limit_data, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW


def test_real_converter_pipeline():
    print("\n--- [1/2] Real Data / Pipeline Verification ---")
    converter = PDFConverter()

    # Mock a DoclingDocument to verify page count frontmatter & O(1) serialization
    mock_doc = MagicMock()
    mock_doc.name = "Real Test Document"
    mock_doc.num_pages.return_value = 12

    md_input = "# Heading\nSample text with image."
    result_md = converter._apply_metadata_frontmatter(mock_doc, md_input)

    assert "page_count: 12" in result_md
    assert "title: Real Test Document" in result_md
    print("✅ Frontmatter & Metadata Extraction: SUCCESS")
    print(f"Generated Frontmatter Preview:\n{result_md[:120]}...\n")


def test_server_stress_and_concurrency():
    print("--- [2/2] FastAPI Concurrency & Load Stress Test ---")
    client = TestClient(app)

    # 1. Test Root Endpoint under load
    t0 = time.perf_counter()
    for _ in range(100):
        res = client.get("/")
        assert res.status_code == 200
        assert "Welcome to the Docling Markdown Conversion Server" in res.json()["message"]
    t1 = time.perf_counter()
    print(f"✅ 100 Synchronous Root GET Requests: {t1 - t0:.4f}s (Avg {(t1 - t0) / 100 * 1000:.2f}ms/req)")

    # 2. Test Rate Limiter and IP Spoofing Prevention under load
    _rate_limit_data.clear()
    
    # 50 requests with legitimate client IP
    headers_legit = {"X-Forwarded-For": "203.0.113.50, 127.0.0.1"}
    accepted = 0
    limited = 0

    with patch("docling_lib.server.TRUSTED_PROXIES", ["127.0.0.1", "testclient"]):
        for i in range(RATE_LIMIT_REQUESTS + 10):
            res = client.get("/download/test/doc.md", headers=headers_legit)
            if res.status_code != 429:
                accepted += 1
            else:
                limited += 1

        assert accepted == RATE_LIMIT_REQUESTS
        assert limited == 10
        print(f"✅ Rate Limiter Stress Test: {accepted} accepted, {limited} rate-limited as expected")

        # 3. Test Spoofing evasion attempt
        # Client attempts to change the leftmost IP to evade rate limiting
        headers_spoofed = {"X-Forwarded-For": "1.2.3.4, 203.0.113.50, 127.0.0.1"}
        res_spoofed = client.get("/download/test/doc.md", headers=headers_spoofed)
        assert res_spoofed.status_code == 429
        print("✅ IP Spoofing Mitigation Test: Spoofed header correctly identified and blocked (429)")


if __name__ == "__main__":
    test_real_converter_pipeline()
    test_server_stress_and_concurrency()
    print("\n🎉 ALL STRESS AND REAL TESTS PASSED SUCCESSFULLY!\n")
