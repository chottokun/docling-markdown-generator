import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from docling_lib.server import app

def test_real_api_conversion():
    print("=== FastAPI 実データ変換エンドポイント動作検証開始 ===")
    client = TestClient(app)

    # 1. ルートエンドポイントの確認
    r_root = client.get("/")
    print(f"1. GET / -> Status: {r_root.status_code}, Response: {r_root.json()}")
    assert r_root.status_code == 200

    # 2. 実ファイル（DOCX）の変換テスト
    sample_file = Path("tests/test_data/sample8_word.docx")
    if not sample_file.exists():
        sample_file = Path("tests/test_data/word_sample.docx")

    print(f"2. アップロードファイル: {sample_file} ({sample_file.stat().st_size} bytes)")

    with open(sample_file, "rb") as f:
        response = client.post(
            "/convert/",
            files={"file": (sample_file.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={
                "table_format": "html",
                "include_page_breaks": "false",
                "include_kv_extraction": "false",
                "vlm_enabled": "false",  # VLM無効で通信遮断
            }
        )

    print(f"3. POST /convert/ -> Status: {response.status_code}")
    assert response.status_code == 200, f"Conversion failed: {response.text}"
    data = response.json()
    print("   レスポンスデータ:", data)
    output_id = data["output_id"]
    markdown_file = data["markdown_file"]

    # 4. 生成された Markdown のダウンロードテスト
    download_url = f"/download/{output_id}/{markdown_file}"
    r_down = client.get(download_url)
    print(f"4. GET {download_url} -> Status: {r_down.status_code}")
    assert r_down.status_code == 200
    print(f"   Markdown 先頭プレビュー:\n---\n{r_down.text[:200]}\n---")

    # 5. Prometheus メトリクスエンドポイントの確認
    r_metrics = client.get("/metrics")
    print(f"5. GET /metrics -> Status: {r_metrics.status_code}")
    assert r_metrics.status_code == 200
    assert "docling_conversions_total" in r_metrics.text
    print(f"   メトリクス出力プレビュー:\n---\n{r_metrics.text[:200]}\n---")

    print("\n✅ FastAPI 実データ変換および全エンドポイントの動作検証が完全に成功しました！")


if __name__ == "__main__":
    test_real_api_conversion()
