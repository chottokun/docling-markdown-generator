import sys
from pathlib import Path

import httpx

API_BASE = "http://localhost:8090"
SAMPLE_PDF = Path("tests/data/real_world/sample5_brochure.pdf")

def main():
    print("=== Testing API VLM Option Request ===")
    if not SAMPLE_PDF.exists():
        print(f"Sample file {SAMPLE_PDF} not found")
        sys.exit(1)

    client = httpx.Client(timeout=120.0)
    
    with open(SAMPLE_PDF, "rb") as f:
        files = {"file": (SAMPLE_PDF.name, f)}
        data = {
            "vlm_enabled": "true",
            "vlm_provider": "ollama",
            "vlm_model": "qwen2-vl:2b",
            "vlm_endpoint": "http://localhost:11434",
            "vlm_prompt": "この画像を簡潔に日本語で説明してください。"
        }
        print("Sending POST /convert/ with VLM enabled...")
        res = client.post(f"{API_BASE}/convert/", files=files, data=data)

    print(f"Status Code: {res.status_code}")
    print(f"Response: {res.text}")

    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    res_json = res.json()
    print(f"✅ VLM Conversion API request succeeded! Output ID: {res_json.get('output_id')}")

if __name__ == "__main__":
    main()
