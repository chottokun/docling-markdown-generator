# CHANGELOG

このプロジェクトのすべての顕著な変更点は、このファイルに記録されます。

フォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) に基づいており、
このプロジェクトは [Semantic Versioning](https://semver.org/lang/ja/) に準拠します。

## [Unreleased]

### セキュリティ (Security)
- `X-Forwarded-For` ヘッダーパース時における IP スプーフィング脆弱性の修正。信頼されたプロキシチェーンを右から左へ辿り、最初に現れた未検証 IP をクライアント IP として抽出する厳格な検証を追加 (PR #201)。

### パフォーマンス (Performance)
- `_save_upload_temp` におけるファイルアップロード保存処理の最適化。不要なループ内での `run_in_threadpool` 呼出を単一のブロック書き込みタスクに一括集約し、保存処理時間を約 84% 削減 (PR #204)。
- `CustomMarkdownPictureSerializer` における画像インデックス検索の $O(1)$ ハッシュマップキャッシュ最適化。大量画像含有ドキュメントでのシリアル化計算量を大幅削減 (PR #203)。
- インメモリ・レートリミッターのクリーンアップ処理 `cleanup_expired_rate_limits` の非同期バックグラウンドタスク化。`await asyncio.sleep(0)` による協調的イベントループ解放により、クリーンアップ時のレスポンス遅延を 98% 以上削減 (PR #199)。

### 追加・改善 (Added / Improved)
- RAG メタデータ抽出の強化: Docling ドキュメントからページ数 (`page_count`) を安全に自動抽出して YAML フロントマターへ埋め込む機能を追加 (PR #202)。
- テストカバレッジの向上: `setup_logging` (`tests/test_config.py`)、ルートエンドポイント・CORS 動作 (`tests/test_root_endpoint.py`)、および VLM base64 エンコード処理 (`tests/test_vlm_and_page_breaks.py`) のユニットテストを追加 (PR #195, #197, #200)。
- 実動作検証・高負荷ストレステスト用スクリプト (`scripts/run_stress_and_integration_test.py`) の追加。

## [0.1.0] - 2026-07-30

### 追加 (Added)
- Docling を利用した PDF / Word / Excel / PowerPoint 等の各種文書から RAG に最適化した Markdown への変換機能。
- CLI コマンド (`docling_converter_cli`) および FastAPI Web サーバーのエンドポイント提供。
- VLM (Ollama / Vision API) と連携した画像の自動説明文（キャプション）生成および相対パス画像リンク埋め込み。
- GPU (CUDA) 互換性チェックおよび非互換環境での CPU 自動フォールバック。
- セキュリティ機能（パス・トラバーサル防止、API キー認証、IP レート制限、Trusted Proxies 設定）。
