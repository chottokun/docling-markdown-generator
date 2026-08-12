# CHANGELOG

このプロジェクトのすべての顕著な変更点は、このファイルに記録されます。

フォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) に基づいており、
このプロジェクトは [Semantic Versioning](https://semver.org/lang/ja/) に準拠します。

## [Unreleased]

### セキュリティ (Security)
- ファイルアップロード時のディスク枯渇（DoS）防止: ASGI レベルの `ContentSizeLimitMiddleware` を実装し、`MAX_UPLOAD_SIZE` を超えるリクエストを一時ファイル作成（スプール）前に `413 Payload Too Large` で即時遮断 (PR #212)。
- Request ID のエントロピー強化: バースデーパラドックスによるフォルダ衝突・データ漏洩を防ぐため、Request ID のエントロピーを 8 バイト (64bit) から 16 バイト (128bit / 32桁HEX) に拡張 (PR #209)。
- VLM ログ出力における API Key 漏洩防止: Google Gemini API キーを URL クエリパラメータから `x-goog-api-key` ヘッダーへ移行し、ログサニタイズ処理に正規表現伏字化（`REDACTED`）を追加 (PR #219)。
- `X-Forwarded-For` ヘッダーパース時における IP スプーフィング脆弱性の修正。信頼されたプロキシチェーンを右から左へ辿り、最初に現れた未検証 IP をクライアント IP として抽出する厳格な検証を追加 (PR #201)。

### パフォーマンス (Performance)
- `EnhancedDoclingConverter` の追加・強化: 画像リンクのカスタマイズ対応。スラッグ決定の優先順位制御（明示指定 `slug` > `assets_dir.name` > ファイル名からの自動クレンジング生成）を追加 (PR #220, #221)。
- 信頼できるプロキシ (`TRUSTED_PROXIES`) 検索の高速化: tuple データ構造化および型判定ファストパスによりホットパスで約 29.2% の速度向上を達成 (PR #208)。
- VLM 画像 base64 エンコードの非同期非ブロック化: 非同期 `generate_caption` 内の CPU/IO 負荷の高い画像エンコードを `asyncio.to_thread` にオフロードし、FastAPI イベントループの滞留を防止 (PR #211)。
- カスタムシリアライザのモデルフィールド初期化最適化: Pydantic モデルフィールド一覧のモジュールレベルキャッシュにより初期化を 18〜20% 高速化 (PR #213)。
- `_save_upload_temp` におけるファイルアップロード保存処理の最適化。不要なループ内での `run_in_threadpool` 呼出を単一のブロック書き込みタスクに一括集約し、保存処理時間を約 84% 削減 (PR #204)。
- `CustomMarkdownPictureSerializer` における画像インデックス検索の $O(1)$ ハッシュマップキャッシュ最適化。大量画像含有ドキュメントでのシリアル化計算量を大幅削減 (PR #203)。
- インメモリ・レートリミッターのクリーンアップ処理 `cleanup_expired_rate_limits` の非同期バックグラウンドタスク化。`await asyncio.sleep(0)` による協調的イベントループ解放により、クリーンアップ時のレスポンス遅延を 98% 以上削減 (PR #199)。

### リファクタリング・コード構造 (Refactoring & Code Health)
- VLM ペイロード作成ロジック `_prepare_rest_payload` のリファクタリング: プロバイダ別ビルダー関数マッピング (`_PROVIDER_BUILDERS`) へ分割整理し可読性と保守性を向上 (PR #210)。
- VLM キャプション生成前処理の共通化: `generate_caption` と `generate_caption_sync` のパラメータ補正・エンドポイント自動解決ロジックを共有ヘルパー関数へ抽出 (PR #205)。

### テスト・品質管理 (Testing Improvement)
- VLM ペイロード作成 (`tests/test_vlm_prepare_payload.py`)、レスポンス抽出 (`tests/test_vlm_extract_response.py`)、例外ハンドリング (`tests/test_vlm_encoding_failure.py`, `tests/test_vlm_async_error.py`) の包括的なユニットテストを追加 (PR #206, #207, #214, #218)。
- 出力ディレクトリ作成 (`tests/test_server_helpers.py`) および HTML テーブルシリアライザ (`tests/test_table_serialization.py`) のエッジケーステストを拡充 (PR #215, #216)。

## [0.1.0] - 2026-07-30

### 追加 (Added)
- Docling を利用した PDF / Word / Excel / PowerPoint 等の各種文書から RAG に最適化した Markdown への変換機能。
- CLI コマンド (`docling_converter_cli`) および FastAPI Web サーバーのエンドポイント提供。
- VLM (Ollama / Vision API) と連携した画像の自動説明文（キャプション）生成および相対パス画像リンク埋め込み。
- GPU (CUDA) 互換性チェックおよび非互換環境での CPU 自動フォールバック。
- セキュリティ機能（パス・トラバーサル防止、API キー認証、IP レート制限、Trusted Proxies 設定）。
