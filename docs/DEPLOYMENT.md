# デプロイメント・ガイド (Deployment Guide)

本サーバーを本番環境やコンテナ環境で運用するためのガイドです。

## 1. 環境変数による設定

以下の環境変数を設定することで、動作をカスタマイズできます。

| 変数名 | デフォルト値 | 説明 |
| :--- | :--- | :--- |
| `DOCLING_UPLOAD_DIR` | `uploads` | アップロードされたファイルの一時保存先 |
| `DOCLING_OUTPUT_DIR` | `output` | 変換済みファイルの保存先 |
| `IMAGE_RESOLUTION_SCALE` | `2.0` | 抽出される画像の解像度倍率 |

### Docker Compose での設定例
```yaml
services:
  app:
    environment:
      - DOCLING_OUTPUT_DIR=/app/data/output
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
