"""Docker コンテナ（http://localhost:8096）に対する E2E 検証スクリプト"""
import json
import urllib.request
import urllib.parse
from pathlib import Path

BASE_URL = "http://localhost:8096"

def main():
    print("=== Docker コンテナ (CUDA 12.4 版) E2E 動作検証開始 ===")
    
    # 1. ルートエンドポイント確認
    req = urllib.request.Request(f"{BASE_URL}/")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        body = json.loads(resp.read().decode())
        print(f"1. GET / -> Status: {resp.status}, Body: {body}")

    # 2. DOCX ファイルのアップロード & 変換 (/convert/)
    sample_file = Path("tests/test_data/sample8_word.docx")
    assert sample_file.exists(), f"{sample_file} が存在しません"

    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    data = []
    data.append(f"--{boundary}".encode())
    data.append(b'Content-Disposition: form-data; name="image_format"\r\n')
    data.append(b"png")
    data.append(f"--{boundary}".encode())
    data.append(b'Content-Disposition: form-data; name="include_images"\r\n')
    data.append(b"true")
    data.append(f"--{boundary}".encode())
    data.append(f'Content-Disposition: form-data; name="file"; filename="{sample_file.name}"'.encode())
    data.append(b"Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n")
    data.append(sample_file.read_bytes())
    data.append(f"--{boundary}--\r\n".encode())
    
    body_bytes = b"\r\n".join(data)

    req = urllib.request.Request(
        f"{BASE_URL}/convert/",
        data=body_bytes,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        res_json = json.loads(resp.read().decode())
        print(f"2. POST /convert/ -> Status: {resp.status}")
        print(f"   Response JSON: {res_json}")
        download_url = res_json.get("download_url")
        assert download_url, "download_url が返されていません"

    # 3. 生成された Markdown のダウンロード (/download/{id}/{file})
    req = urllib.request.Request(f"{BASE_URL}{download_url}")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        md_content = resp.read().decode("utf-8")
        print(f"3. GET {download_url} -> Status: {resp.status}")
        print(f"   Markdown 先頭プレビュー:\n---\n{md_content[:150]}\n---")
        assert "Sample Document" in md_content

    # 4. Prometheus メトリクスの取得 (/metrics)
    req = urllib.request.Request(f"{BASE_URL}/metrics")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        metrics_text = resp.read().decode("utf-8")
        print(f"4. GET /metrics -> Status: {resp.status}")
        assert 'docling_conversions_total{status="success"} 1' in metrics_text
        print("   メトリクス: docling_conversions_total{status=\"success\"} 1 を確認")

    print("\n🎉 Docker コンテナ (CUDA 12.4 版) 上での全 API E2E テストに完全成功しました！")

if __name__ == "__main__":
    main()
