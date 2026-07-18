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
これらのオプションを設定することで、より高度な解析機能やGPUによるハードウェア加速を制御できます（計算リソースをより多く消費します）。

| 変数名 | デフォルト値 | 説明 |
| :--- | :--- | :--- |
| `DOCLING_DO_FORMULA` | `True` | 数式の抽出を有効にする。 |
| `DOCLING_DO_OCR` | `True` | OCR（光学文字認識）を有効にする。 |
| `DOCLING_DO_CHART` | `False` | 図表（チャート）の抽出と解析を有効にする。 |
| `DOCLING_DO_CODE` | `False` | コードブロックの高度な認識と強化を有効にする。 |
| `DOCLING_USE_GPU` | `True` | GPU（CUDA）アクセラレーションの利用を制御する。`False`に設定した場合、GPU検証をバイパスして強制的にCPUモードで動作します。 |
| `DOCLING_NUM_THREADS` | `4` | CPU/GPU前処理等で使用される演算スレッド数。 |
| `DOCLING_CUDA_FLASH_ATTENTION` | `False` | サポートされているハイエンドGPUでFlashAttention2を有効化し、推論の高速化とメモリ消費の削減を図る。 |
| `DOCLING_TABLE_FORMAT` | `html` | テーブルのシリアライズ形式（`html` または `markdown`）。 |
| `DOCLING_VLM_ENABLED` | `False` | ローカルの Ollama 等のVLMを用いた画像説明（キャプション）生成を有効化する。 |
| `DOCLING_VLM_MODEL` | `qwen2-vl:2b` | 利用するVLMモデル名。 |
| `DOCLING_VLM_ENDPOINT` | `http://localhost:11434` | Ollama などのVLM APIのエンドポイントURL。 |
| `DOCLING_VLM_PROMPT` | （画像説明指示文） | VLMへ送信する指示プロンプト。 |
| `DOCLING_INCLUDE_PAGE_BREAKS` | `False` | Markdown内のページ境界に `<!-- PAGE_BREAK: Page N -->` コメントを埋め込む（RAG等でのチャンク分割用）。 |
| `DOCLING_INCLUDE_KV_EXTRACTION` | `False` | YAMLメタデータやヘッダー部に重要情報（KV抽出プレースホルダー）を埋め込む。 |



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

- **CPU/GPUと自動フォールバック**: DoclingはOCRやレイアウト解析に多大なリソースを消費します。
  - **明示的な制御**: 環境変数 `DOCLING_USE_GPU` を `False` に設定することで、GPUの利用を明示的に無効化し、強制的にCPUで動作させることができます。
  - **自動フォールバック**: GPU（CUDA）が利用可能な環境では自動的に高速化されますが、PyTorchのCUDAビルドとインストールされている物理GPUのCompute Capability（CC）に不整合がある場合（例: 古いGPUでの実行時エラー等）、システムは実行時クラッシュを避けるために起動時にダミーテンソル演算を用いて互換性を自動検証し、問題が検出された場合は安全に**CPUモードへ自動フォールバック**します。
  - **GPU性能の最大化**: 高性能なGPU環境（CC >= 7.5）では、環境変数 `DOCLING_CUDA_FLASH_ATTENTION` を `True` に設定することで FlashAttention2 を有効化し、推論の高速化とVRAM効率化が可能です。また `DOCLING_NUM_THREADS` で処理用スレッド数を最適化できます。
- **並行処理**: 内部的に `threading.Lock` を使用しているため、単一プロセス内でのドキュメント解析（モデル推論）は順次実行されます。ただし、抽出画像に対するVLM呼び出し処理は `ThreadPoolExecutor` を用いて並列に処理され、I/Oブロッキングを低減します。高い同時接続スループットが必要な場合は、複数のコンテナを起動し、ロードバランサーで負荷分散してください。

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
