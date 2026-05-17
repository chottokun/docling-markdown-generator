# Docling Markdown Generator

Docling（v2.x）を基盤とした、高度な構造化ドキュメント変換エンジン。PDF、Office（DOCX/PPTX/XLSX）から、LLMフレンドリーなMarkdown、抽出画像、およびHTML構造化テーブルを生成します。

本プロジェクトは、単なるラッパーを超え、エンタープライズレベルのデプロイメントに必要となる**セキュリティ、スケーラビリティ、および観測性**を備えた変換パイプラインを提供します。

---

## 🏗 アーキテクチャと設計思想

- **シングルトン・コンバーター・パターン**: `PDFConverter` インスタンスをシングルトンとして管理し、重いモデル（OCR, VLM, Table Analysis）の初期化コストを最小化。設定変更（OCR ON/OFF等）を検知した場合のみ、インテリジェントに再初期化を行います。
- **非同期非ブロッキングI/O**: FastAPI + `run_in_threadpool` によるマルチスレッド実行。CPU集約型の変換タスク実行中も、APIサーバーのイベントループをブロッキングしません。
- **プラットフォーム・アグノスティック**: `uv` による決定論的なパッケージ管理。CUDA環境下ではGPU加速、非CUDA環境下ではCPUへ自動フォールバックします。

## 🔒 セキュリティ・エンジニアリング

セキュリティを「後付け」ではなくコア機能として実装しています：

- **API Key Authentication**: `X-API-Key` ヘッダーによるリクエスト認証（条件付き有効化）。
- **IP-based Rate Limiting**: 過度なリソース消費を防ぐためのIPベースのインメモリ・レートリミッター。
- **Path Traversal Protection**: 入出力パスに対する `resolve()` および `is_relative_to()` による厳格なサンドボックス化。
- **Injection Mitigation**: 
  - **Log Injection**: ログ出力前のメタデータサニタイズ。
  - **YAML Frontmatter Injection**: ドキュメント名等のメタデータによるYAML構造破壊を防止。
- **Restrictive CORS**: ホワイトリスト形式による厳密なオリジン・メソッド・ヘッダー制御。

## ⚡ パフォーマンス最適化

- **Streaming Download**: サンプルファイル等のダウンロード時、メモリ消費を最大約70%削減するストリーミング処理の実装。
- **Zero-Dependency Office Conversion**: `docling` のネイティブパーサーにより、LibreOffice等の外部バイナリ不要でOfficeファイルを処理。
- **Efficient Re-initialization**: パイプライン設定（画像スケール、OCR有無等）の差分を検知し、必要な場合のみエンジンをリロード。

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
docker-compose up -d --build
```
*APIサーバーはデフォルトで `8000` ポートで待機します。*

## 📖 技術ドキュメント

詳細な仕様については `docs/` ディレクトリを参照してください：

- **[Unique Features (FEATURES.md)](docs/FEATURES.md)**: セキュリティとパフォーマンスの詳細実装。
- **[API Reference (API_REFERENCE.md)](docs/API_REFERENCE.md)**: 認証・レート制限を含むエンドポイント仕様。
- **[Markdown Specification (MARKDOWN_SPEC.md)](docs/MARKDOWN_SPEC.md)**: 生成されるMarkdownの構造定義。
- **[Deployment Guide (DEPLOYMENT.md)](docs/DEPLOYMENT.md)**: 環境変数と本番運用のための構成。

## 🧪 テストと検証

TDDに基づき、以下のテストスイートを運用しています：

- **Unit Tests**: モジュールごとのロジック検証（`uv run pytest tests/test_converter_units.py`）。
- **E2E Real World**: 実データを用いたEnd-to-End検証（`CUDA_VISIBLE_DEVICES="" uv run pytest tests/e2e_real_world.py`）。
- **Security Tests**: 脆弱性再現スクリプトによる回帰テスト（`tests/test_security_auth_rate_limit.py` 等）。

---
**License**: MIT (docling, FastAPI 等の依存先に準拠)
