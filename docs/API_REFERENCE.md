# APIリファレンス (API Reference)

FastAPIによるMarkdown変換サーバーのAPI仕様です。

## 1. ドキュメント変換エンドポイント

ドキュメントをアップロードし、Markdownおよび画像群を生成します。

- **URL**: `/convert/`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **Request Body**:
  - `file` (必須): 変換対象のドキュメント（.pdf, .docx, .pptx, .xlsx 等）
  - `table_format` (任意): テーブルの出力形式。`html` または `markdown`。
  - `include_page_breaks` (任意): ページ境界マーカー `<!-- PAGE_BREAK: Page N -->` を有効にするかどうか。`true` または `false`。
  - `include_kv_extraction` (任意): 重要情報のキー・バリュー抽出用セクションを追加するかどうか。`true` または `false`。
  - `vlm_enabled` (任意): 画像のキャプション（日本語）自動生成を有効にするかどうか。`true` または `false`。
  - `vlm_model` (任意): キャプション生成に使用するVLMモデル名（例: `qwen2-vl:2b`, `qwen3.5:4b`）。
  - `vlm_endpoint` (任意): VLM APIのエンドポイント（例: `http://localhost:11434`）。
  - `vlm_prompt` (任意): VLMへの指示プロンプト。
  - `num_threads` (任意): 演算に使用するスレッド数（整数値）。
  - `cuda_use_flash_attention` (任意): FlashAttention2 を有効にするかどうか。`true` または `false`。


### レスポンス (JSON)
成功時 (200 OK):
```json
{
  "message": "Conversion successful",
  "markdown_file": "processed_document.md",
  "output_id": "1a2b3c4d5e6f",
  "download_url": "/download/1a2b3c4d5e6f/processed_document.md"
}
```

### cURL 例
```bash
curl -X POST -F "file=@sample.pdf" http://localhost:8000/convert/
```

## 2. ファイルダウンロードエンドポイント

変換済みのファイル（Markdownまたは画像）をダウンロードします。

- **URL**: `/download/{request_id}/{filename}`
- **Method**: `GET`
- **Headers**:
  - `X-API-Key` (Optional): サーバーでAPIキーが設定されている場合に必須。
- **Path Parameters**:
  - `request_id`: 変換時に割り振られた一意のID
  - `filename`: 取得するファイル名（例: `processed_document.md` や `images/image_1.png`）
- **Rate Limit**: `/convert/` エンドポイントと同様にIPベースのレート制限が適用されます。

### cURL 例
```bash
curl -H "X-API-Key: your_api_key_here" -O http://localhost:8000/download/1a2b3c4d5e6f/processed_document.md
```

## 3. エラーコード

- **400 Bad Request**: サポートされていない拡張子、または無効なリクエストパラメータ。
- **401 Unauthorized**: 無効または未指定のAPIキー。
- **404 Not Found**: ファイルが存在しない、または無許可のパスアクセス（Path Traversal対策）。
- **429 Too Many Requests**: 短時間での過剰なリクエスト送信によるレート制限の超過。
- **500 Internal Server Error**: 変換エンジンの内部エラー。

## 4. セキュリティと並行処理

- **パス・トラバーサル保護**: すべてのリクエストパスは検証され、指定されたディレクトリ外のファイルへのアクセスは拒否されます。
- **スレッドセーフ**: 共有コンバーターへのアクセスはロック制御されており、並行リクエスト時も安全に動作します。
- **非同期処理**: 変換処理はスレッドプールで実行されるため、サーバー全体の応答性は維持されます。
