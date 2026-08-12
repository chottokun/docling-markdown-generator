# APIリファレンス (API Reference)

FastAPIによるDocling Markdown Conversion ServerのAPI仕様および各種言語からの利用ガイドです。

---

## 📌 目次
1. [概要・環境設定](#1-概要環境設定)
2. [ドキュメント変換エンドポイント (`POST /convert/`)](#2-ドキュメント変換エンドポイント-post-convert)
3. [ファイルダウンロードエンドポイント (`GET /download/{request_id}/{filename}`)](#3-ファイルダウンロードエンドポイント-get-downloadrequest_idfilename)
4. [ヘルスチェックエンドポイント (`GET /`)](#4-ヘルスチェックエンドポイント-get-)
5. [クライアント利用例 (cURL / Python / JavaScript)](#5-クライアント利用例-curl--python--javascript)
6. [エラーレスポンス一覧](#6-エラーレスポンス一覧)
7. [セキュリティと並行処理制御](#7-セキュリティと並行処理制御)

---

## 1. 概要・環境設定

本APIサーバーは、PDF/Word/Excel/PowerPointなどの多様なドキュメントをアップロードし、RAGに最適化された構造化Markdown、抽出画像、および表データ（HTML/Markdown）へ変換します。

### ベースURL
- **ローカル直接起動 (uvicorn)**: `http://localhost:8000`
- **Docker Compose起動**: `http://localhost:8090` *(docker-compose.ymlのポートマッピング 8090:8000 による)*

### 認証方法
サーバー環境変数 `DOCLING_API_KEY` が設定されている場合、全リクエストに以下のHTTPヘッダーが必要です。
```http
X-API-Key: your_configured_api_key
```

---

## 2. ドキュメント変換エンドポイント (`POST /convert/`)

ファイルおよび各種オプションパラメータを送信し、Markdown変換処理を実行します。

- **Method**: `POST`
- **Path**: `/convert/`
- **Content-Type**: `multipart/form-data`
- **Headers**:
  - `X-API-Key` (任意/設定時必須): APIキー

### リクエストパラメータ (Form Data)

| パラメータ名 | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| `file` **(必須)** | File | - | 変換対象のファイル（`.pdf`, `.docx`, `.pptx`, `.xlsx`） |
| `table_format` | string | `"html"` | 表の出力形式 (`html` または `markdown`) |
| `include_page_breaks` | boolean | `true` | 改ページマーカー `<!-- PAGE_BREAK: Page N -->` の差し込み有無 |
| `include_kv_extraction` | boolean | `false` | キー・バリュー抽出用セクションの追加有無 |
| `vlm_enabled` | boolean | `false` | Vision-Language Model (VLM) による画像説明文自動生成の有無 |
| `vlm_provider` | string | `"ollama"` | VLMプロバイダ (`ollama`, `openai`, `gemini`, `anthropic` 等) |
| `vlm_model` | string | `"qwen2-vl:2b"` | 使用するVLMモデル名 |
| `vlm_endpoint` | string | `"http://localhost:11434"` | VLMサービスのエンドポイント |
| `vlm_prompt` | string | *標準プロンプト* | VLMへの指示プロンプト |
| `vlm_max_concurrent` | integer | `4` | VLM APIへの同時並列リクエスト上限数 |
| `num_threads` | integer | CPU自動判定 | 計算処理用スレッド数 |
| `cuda_use_flash_attention` | boolean | `false` | FlashAttention2の有効化（対応GPU環境のみ） |

### 成功時レスポンス (200 OK)
```json
{
  "message": "Conversion successful",
  "markdown_file": "sample.md",
  "output_id": "8f3b2a1c9d4e5f60",
  "download_url": "/download/8f3b2a1c9d4e5f60/sample.md"
}
```

---

## 3. ファイルダウンロードエンドポイント (`GET /download/{request_id}/{filename}`)

変換結果（Markdownファイルまたは抽出された画像ファイル）を取得・ダウンロードします。

- **Method**: `GET`
- **Path**: `/download/{request_id}/{filename}`
- **Path Parameters**:
  - `request_id`: `/convert/` レスポンスで返された一意の文字列 ID
  - `filename`: 取得対象のファイル名 (`sample.md` や `images/image_1.png` 等)

### 成功時レスポンス (200 OK)
指定したファイルのバイナリ/テキストデータストリームを返却します。

---

## 4. ヘルスチェックエンドポイント (`GET /`)

サーバーの稼働状態を確認します。

- **Method**: `GET`
- **Path**: `/`

### 成功時レスポンス (200 OK)
```json
{
  "message": "Welcome to the Docling Markdown Conversion Server"
}
```

---

## 5. クライアント利用例 (cURL / Python / JavaScript)

### cURL による例

#### 基本的な変換リクエスト
```bash
curl -X POST "http://localhost:8090/convert/" \
  -F "file=@/path/to/document.pdf"
```

#### 認証キー・オプション付きリクエスト
```bash
curl -X POST "http://localhost:8090/convert/" \
  -H "X-API-Key: your_secret_key" \
  -F "file=@/path/to/financial_report.xlsx" \
  -F "table_format=html" \
  -F "include_page_breaks=true"
```

#### 成果物のダウンロード
```bash
curl -H "X-API-Key: your_secret_key" \
  -o result.md \
  "http://localhost:8090/download/8f3b2a1c9d4e5f60/sample.md"
```

---

### Python (httpx) による例

```python
import httpx

API_BASE_URL = "http://localhost:8090"
API_KEY = "your_secret_key"  # 未設定時は None

headers = {}
if API_KEY:
    headers["X-API-Key"] = API_KEY

# 1. 変換リクエスト
with open("sample.pdf", "rb") as f:
    files = {"file": ("sample.pdf", f, "application/pdf")}
    data = {
        "table_format": "html",
        "include_page_breaks": "true",
    }
    response = httpx.post(f"{API_BASE_URL}/convert/", headers=headers, files=files, data=data)
    response.raise_for_status()

result = response.json()
print("Conversion Response:", result)

# 2. Markdownダウンロード
download_url = f"{API_BASE_URL}{result['download_url']}"
dl_response = httpx.get(download_url, headers=headers)
dl_response.raise_for_status()

with open(result["markdown_file"], "w", encoding="utf-8") as out_f:
    out_f.write(dl_response.text)

print(f"Saved to {result['markdown_file']}")
```

---

### JavaScript (Fetch / Node.js) による例

```javascript
const fs = require('fs');
const FormData = require('form-data');
const fetch = require('node-fetch');

async function convertDocument() {
  const form = new FormData();
  form.append('file', fs.createReadStream('sample.pdf'));
  form.append('table_format', 'html');

  // 1. 変換リクエスト
  const res = await fetch('http://localhost:8090/convert/', {
    method: 'POST',
    body: form,
    headers: {
      ...form.getHeaders(),
      // 'X-API-Key': 'your_secret_key'
    }
  });

  if (!res.ok) {
    throw new Error(`HTTP Error: ${res.status}`);
  }

  const result = await res.json();
  console.log('Result:', result);

  // 2. ダウンロード
  const dlRes = await fetch(`http://localhost:8090${result.download_url}`);
  const markdownText = await dlRes.text();
  fs.writeFileSync(result.markdown_file, markdownText);
}

convertDocument().catch(console.error);
```

---

## 6. エラーレスポンス一覧

| HTTP ステータス | エラー内容 | レスポンス例 | 対処法 |
|---|---|---|---|
| **400 Bad Request** | 未サポートの拡張子 / 不正な引数 | `{"detail": "Unsupported file format. Supported: ['.pdf', '.docx', ...]"}` | 許可されたファイル拡張子でアップロードしてください |
| **401 Unauthorized** | APIキーが不足または不正 | `{"detail": "Invalid or missing API Key."}` | リクエストヘッダーに正しい `X-API-Key` を指定してください |
| **404 Not Found** | ファイルが存在しない / パストラバーサル試行 | `{"detail": "File not found."}` | 正しい `request_id` と `filename` を指定してください |
| **413 Payload Too Large** | ファイルサイズが上限超過 | `{"detail": "Payload Too Large. Maximum size is 52428800 bytes."}` | `MAX_UPLOAD_SIZE`（デフォルト50MB）以下のファイルを使用してください |
| **429 Too Many Requests** | レート制限の超過 | `{"detail": "Too Many Requests. Please try again later."}` | 一定時間（1分）置いてから再度リクエストしてください |
| **500 Internal Server Error** | サーバー内部エラー | `{"detail": "An internal error occurred during conversion."}` | サーバーのログを確認してください |

---

## 7. セキュリティと並行処理制御

- **Path Traversal 防止**: `request_id` および `filename` のパストラバーサル文字（`../` 等）を自動検出し、絶対パス検証 (`is_relative_to`) で隔離ディレクトリ外へのアクセスを完全遮断。
- **動的セマフォ制御**: 利用可能メモリ量に応じ、同時の重い変換処理プロセス数を自動的に制限（OOMクラッシュ防止）。
- **IPスプーフィング対策**: 信頼済みプロキシ（`TRUSTED_PROXIES`）経由の通信のみ `X-Forwarded-For` のクライアントIPを参照。
