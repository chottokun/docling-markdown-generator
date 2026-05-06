# デプロイメント・ガイド (Deployment Guide)

本サーバーを本番環境やコンテナ環境で運用するためのガイドです。

## 1. 環境変数による設定

以下の環境変数を設定することで、動作をカスタマイズできます。

| 変数名 | デフォルト値 | 説明 |
| :--- | :--- | :--- |
| `DOCLING_UPLOAD_DIR` | `uploads` | アップロードされたファイルの一時保存先 |
| `DOCLING_OUTPUT_DIR` | `output` | 変換済みファイルの保存先 |
| `DOCLING_MAX_UPLOAD_SIZE` | `20971520` | 最大アップロードサイズ（バイト単位）。デフォルトは20MB。 |
| `DOCLING_CORS_ORIGINS` | `*` | 許可するCORSオリジンのカンマ区切りリスト。 |
| `IMAGE_RESOLUTION_SCALE` | `2.0` | 抽出される画像の解像度倍率。 |

### docling v2.x 拡張オプション
これらのオプションを `True` に設定することで、より高度な解析が可能になります（計算リソースをより多く消費します）。

| 変数名 | デフォルト値 | 説明 |
| :--- | :--- | :--- |
| `DOCLING_DO_FORMULA` | `True` | 数式の抽出を有効にする。 |
| `DOCLING_DO_OCR` | `True` | OCR（光学文字認識）を有効にする。 |
| `DOCLING_DO_CHART` | `False` | 図表（チャート）の抽出と解析を有効にする。 |
| `DOCLING_DO_CODE` | `False` | コードブロックの高度な認識と強化を有効にする。 |

### Docker Compose での設定例
```yaml
services:
  app:
    environment:
      - DOCLING_OUTPUT_DIR=/app/data/output
      - DOCLING_CORS_ORIGINS=https://app.example.com,https://api.example.com
      - DOCLING_DO_CHART=True
      - IMAGE_RESOLUTION_SCALE=3.0
    volumes:
      - ./data:/app/data
```

## 2. スケーリングとパフォーマンス

- **CPU/GPU**: DoclingはOCRやレイアウト解析にリソースを消費します。GPU (CUDA) が利用可能な環境では、自動的に高速化されます。
- **並行処理**: 内部的に `threading.Lock` を使用しているため、単一プロセス内での変換は順次実行されます。高いスループットが必要な場合は、複数のコンテナを起動し、ロードバランサーで振り分けてください。

## 3. ストレージ管理

変換されたファイルは `OUTPUT_DIR` に蓄積されます。
定期的なクリーンアップ（例: 24時間以上経過したディレクトリの削除）を行うサイドカーコンテナや cron ジョブの運用を推奨します。

### クリーンアップのコマンド例
```bash
find output/* -type d -ctime +1 -exec rm -rf {} +
```

## 4. ヘルスチェック

サーバーが正常に稼働しているか確認するには、ルートエンドポイントへの GET リクエストを使用してください。
```bash
curl -f http://localhost:8000/ || exit 1
```
