# APIリファレンス (API Reference)

FastAPIによるMarkdown変換サーバーのAPI仕様です。

## 1. ドキュメント変換エンドポイント

ドキュメントをアップロードし、Markdownおよび画像群を生成します。

- **URL**: `/convert/`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **Request Body**:
  - `file`: 変換対象のドキュメント（.pdf, .docx, .pptx, .xlsx）

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
- **Path Parameters**:
  - `request_id`: 変換時に割り振られた一意のID
  - `filename`: 取得するファイル名（例: `processed_document.md` や `images/image_1.png`）

### cURL 例
```bash
curl -O http://localhost:8000/download/1a2b3c4d5e6f/processed_document.md
```

## 3. エラーコード

- **400 Bad Request**: サポートされていない拡張子、または無効なリクエストパラメータ。
- **404 Not Found**: ファイルが存在しない、または無許可のパスアクセス（Path Traversal対策）。
- **500 Internal Server Error**: 変換エンジンの内部エラー。

## 4. セキュリティと並行処理

- **パス・トラバーサル保護**: すべてのリクエストパスは検証され、指定されたディレクトリ外のファイルへのアクセスは拒否されます。
- **スレッドセーフ**: 共有コンバーターへのアクセスはロック制御されており、並行リクエスト時も安全に動作します。
- **非同期処理**: 変換処理はスレッドプールで実行されるため、サーバー全体の応答性は維持されます。
