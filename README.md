# Docling Markdown Generator

Docling（v2.x）を基盤とした、高度な構造化ドキュメント変換エンジン。PDF、Office（DOCX/PPTX/XLSX）から、LLMフレンドリーなMarkdown、抽出画像、およびHTML構造化テーブルを生成します。

本プロジェクトは、単なるラッパーを超え、エンタープライズレベルのデプロイメントに必要となる**セキュリティ、スケーラビリティ、および観測性**を備えた変換パイプラインを提供します。

---

## 🏗 アーキテクチャと設計思想

- **マルチプロセス並列化エンジン (ProcessPoolExecutor)**: GIL (Global Interpreter Lock) のボトルネックを完全に排除し、`spawn` コンテキストによる独立したワーカープロセスで変換パイプラインを実行。APIサーバーの応答性を常に最高レベルに維持します。
- **メモリ適応型動的セマフォ制御**: `psutil` を用いてシステムの利用可能 RAM 量を追跡し、同時並列実行数を動的に制御して高負荷時の OOM (Out of Memory) キラーによるダウンを防止します。
- **非同期 I/O 保存 (`aiofiles`)**: アップロードファイルをメモリに乗せずに 1MB 単位の非同期ストリーミングでディスクへ一時保存し、DoS 攻撃や過度なメモリ消費を防御。
- **プラットフォーム・アグノスティック & GPU自動フォールバック**: `is_cuda_compatible()` により、CUDA Compute Capability >= 7.5 の高性能 GPU で加速しつつ、古い GPU や非 GPU 環境では自動的に CPU モードへフォールバックします。

## 🔒 セキュリティ・エンジニアリング

セキュリティを「後付け」ではなくコア機能として実装しています：

- **API Key Authentication**: `X-API-Key` ヘッダーによるリクエスト認証（条件付き有効化）。
- **IP-based Rate Limiting & Spoofing Defense**: 信頼されたプロキシチェーン（`X-Forwarded-For`）を右から左へ辿る厳格な IP 検証による IP スプーフィング回避防止、および非同期バックグラウンドタスクによるメモリクリーンアップ。
- **Path Traversal Protection**: 入出力パスに対する `resolve()` および `is_relative_to()` による厳格なサンドボックス化。
- **Injection Mitigation**: 
  - **Log Injection**: ログ出力前のメタデータサニタイズ。
  - **YAML Frontmatter Injection**: ドキュメント名等のメタデータによるYAML構造破壊を防止。
- **Restrictive CORS**: ホワイトリスト形式による厳密なオリジン・メソッド・ヘッダー制御。

## ⚡ パフォーマンス最適化

- **Fast File Upload Saving**: 単一のブロック書き込みタスクによる保存最適化（コンテキストスイッチ削除によりファイル保存レイテンシを約 84% 削減）。
- **$O(1)$ Picture Serialization**: 画像参照インデックスをハッシュマップで事前生成し、$O(N^2)$ 線形探索を廃止してシリアル化速度を大幅向上。
- **VLM Caption Prefetching**: ドキュメント内から切り出した複数画像に対し、`ThreadPoolExecutor` を用いて Ollama や各種クラウド API 等へのVLMリクエストを**非同期並列で一括事前取得 (Prefetch)** しキャッシュ。直列実行による同期ブロッキングを排除し、処理時間を大幅に短縮します。
- **マルチプロバイダ VLM 連携と流量制御 (Rate Limiting)**: ローカルの Ollama に加え、OpenAI, Google Gemini, Anthropic Claude、および vLLM/llama.cpp などの OpenAI 互換のローカル推論サーバーをサポート。さらに、各プロバイダ・エンドポイントごとの接続制限に対応したセマフォによる並列流量制御を行います。
- **GPU Accelerator Tuning**: `DOCLING_NUM_THREADS` (CPU処理スレッド数) や `DOCLING_CUDA_FLASH_ATTENTION` (FlashAttention2トグル) の環境変数制御をサポートし、高性能GPUのハードウェア性能を最大化させます。
- **Streaming Download**: サンプルファイル等のダウンロード時、メモリ消費を最大約70%削減するストリーミング処理の実装。
- **Zero-Dependency Office Conversion**: `docling` のネイティブパーサーにより、LibreOffice等の外部バイナリ不要でOfficeファイルを処理。
- **Efficient Re-initialization**: パイプライン設定（画像スケール、OCR有無、VLM有無、スレッド数等）の差分を検知し、必要な場合のみエンジンをリロード。


## 🚀 クイックスタート

### 開発環境のセットアップ

```bash
# uvを使用した依存関係のインストール
uv sync --extra test
```

### CLI実行
```bash
uv run docling_converter_cli input.pdf -o ./output
```

### Dockerコンテナの実行
```bash
# 1. 環境変数設定ファイルの作成（必要に応じて .env 内で設定調整）
cp .env.example .env

# 2. docling-server の起動
docker compose up -d --build
```
*APIサーバーはホストの `8090` ポート（コンテナ内 `8000`）で待機します。*

## 📖 技術ドキュメント

詳細な仕様については `docs/` ディレクトリおよび変更履歴を参照してください：

- **[Changelog (CHANGELOG.md)](CHANGELOG.md)**: バージョンごとの機能追加・修正・変更履歴。
- **[GPU Testing & Acceleration (GPU_TESTING.md)](docs/GPU_TESTING.md)**: GPU/CUDA利用時の動作仕様、VRAM管理、自動フォールバック、およびテスト手順。
- **[Unique Features (FEATURES.md)](docs/FEATURES.md)**: セキュリティとパフォーマンスの詳細実装。
- **[API Reference (API_REFERENCE.md)](docs/API_REFERENCE.md)**: 認証・レート制限を含むエンドポイント仕様。
- **[Markdown Specification (MARKDOWN_SPEC.md)](docs/MARKDOWN_SPEC.md)**: 生成されるMarkdownの構造定義。
- **[Deployment Guide (DEPLOYMENT.md)](docs/DEPLOYMENT.md)**: 環境変数と本番運用のための構成。

## 🧪 テストと検証

TDDに基づき、以下のテストスイートおよび検証プロセスを運用しています：

- **Unit / Parallelization Tests**: マルチプロセス並列化およびモジュールロジックの検証（`uv run pytest`）。
- **GPU Acceleration Tests**: GPU環境および自動フォールバック動作の検証（`DOCLING_USE_GPU=True uv run pytest tests/test_device_verification.py`）。詳細は [GPU_TESTING.md](docs/GPU_TESTING.md) を参照。
- **E2E Real World**: 実データを用いたEnd-to-End検証（`uv run pytest tests/test_parallelization.py`）。
- **Security Tests**: 脆弱性再現スクリプトによる回帰テスト（`tests/test_security_auth_rate_limit.py` 等）。
- **Excel/Matrix Tests (Docker経由)**: 複雑なマトリクスを持つExcelファイル等の高精度変換検証：
  ```bash
  docker compose run --user root --entrypoint "python scripts/verify_excel.py" docling-server
  ```

## 🔮 今後の課題 (Roadmap)

本ライブラリのさらなる拡張とエンタープライズでの最適化に向けて、以下のロードマップを予定しています。

- **図表 (Chart/Table) と VLM 連携の緊密化**: 抽出画像だけでなく、切り出されたグラフ（Chart）や複雑なHTMLテーブルに対し自動的にVLMによる高度な日本語サマリーを生成・埋め込む機能の拡張。

## 📄 ライセンス

本プロジェクトは **MIT License** の下で公開されています。

主要な使用ライブラリおよびそのライセンス：
- **docling** (v2.x): MIT License
- **docling-core**: MIT License
- **fastapi**: MIT License
- **pytorch (torch)**: BSD-3-Clause License
- **uvicorn**: BSD-3-Clause License
- **python-multipart**: Apache-2.0 License
- **httpx**: BSD-3-Clause License
