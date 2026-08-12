import sys
import time
from pathlib import Path

import httpx

API_BASE = "http://localhost:8090"
REAL_WORLD_DIR = Path("tests/data/real_world")
OUTPUT_DIR = Path("test_api_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def print_result(test_name: str, passed: bool, detail: str = ""):
    symbol = "✅ PASSED" if passed else "❌ FAILED"
    print(f"[{symbol}] {test_name}: {detail}")

def main():
    print("=== Docling Server Docker API Integration Test ===")
    client = httpx.Client(timeout=180.0)

    # 1. Health check test
    try:
        res = client.get(f"{API_BASE}/")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert "Welcome" in res.json().get("message", ""), "Unexpected message"
        print_result("1. GET / (Health Check)", True, res.text)
    except Exception as e:
        print_result("1. GET / (Health Check)", False, str(e))
        sys.exit(1)

    # 2. Invalid File Extension Test
    try:
        files = {"file": ("test.invalid_ext", b"dummy content", "text/plain")}
        res = client.post(f"{API_BASE}/convert/", files=files)
        assert res.status_code == 400, f"Expected 400, got {res.status_code}"
        print_result("2. POST /convert/ (Invalid Ext 400 Test)", True, res.text)
    except Exception as e:
        print_result("2. POST /convert/ (Invalid Ext 400 Test)", False, str(e))

    # 3. Real World Files Test
    test_files = [
        "sample1_simple.pdf",
        "sample5_brochure.pdf",
        "sample8_word.docx",
        "sample7_financial.xlsx",
        "gijutsu_matrix_20260214.xlsx"
    ]

    for filename in test_files:
        filepath = REAL_WORLD_DIR / filename
        if not filepath.exists():
            print_result(f"3. Real World Test: {filename}", False, f"File not found: {filepath}")
            continue

        print(f"\n--- Testing Conversion for: {filename} ---")
        start_time = time.time()
        try:
            with open(filepath, "rb") as f:
                files = {"file": (filepath.name, f)}
                data = {
                    "table_format": "html",
                    "include_page_breaks": "true",
                }
                res = client.post(f"{API_BASE}/convert/", files=files, data=data)
            
            elapsed = time.time() - start_time
            assert res.status_code == 200, f"HTTP {res.status_code}: {res.text}"
            res_data = res.json()
            
            assert "output_id" in res_data
            assert "download_url" in res_data
            assert "markdown_file" in res_data
            print_result(f"API Post ({filename})", True, f"Took {elapsed:.2f}s, Output ID: {res_data['output_id']}")

            # 4. Download Converted Markdown Test
            dl_url = f"{API_BASE}{res_data['download_url']}"
            dl_res = client.get(dl_url)
            assert dl_res.status_code == 200, f"Download failed HTTP {dl_res.status_code}"
            
            saved_md_path = OUTPUT_DIR / f"{filepath.stem}_output.md"
            saved_md_path.write_bytes(dl_res.content)
            
            md_content = dl_res.text
            print_result(f"Download MD ({filename})", True, f"Saved to {saved_md_path} ({len(md_content)} bytes)")

            # Simple inspection of content
            lines = [line for line in md_content.splitlines() if line.strip()]
            preview = " | ".join(lines[:2]) if lines else "Empty"
            print(f"   [Inspect] Output Preview: {preview[:120]}...")

        except Exception as e:
            print_result(f"Conversion ({filename})", False, str(e))

    print("\n=== All Tests Completed ===")

if __name__ == "__main__":
    main()
