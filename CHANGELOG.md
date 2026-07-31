# CHANGELOG

このプロジェクトのすべての顕著な変更点は、このファイルに記録されます。

フォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) に基づいており、
このプロジェクトは [Semantic Versioning](https://semver.org/lang/ja/) に準拠します。

## [Unreleased]

### 追加 (Added)
- `ProcessPoolExecutor` (`spawn` コンテキスト) によるマルチプロセス並列化変換エンジンを導入し、GIL ボトルネックを完全解消。
- `psutil` に基づくメモリ適応型動的セマフォ制御 (`get_dynamic_semaphore_limit`) による高負荷時の OOM キラー保護。
- `aiofiles` によるアップロードファイルの非同期ディスクストリーミング保存機能。
- GPU (CUDA) 環境を想定した詳細動作仕様、VRAM管理、およびテストガイドライン (`docs/GPU_TESTING.md`) を追加。
- `pyproject.toml` への `pythonpath = ["."]` 追加による自動モジュール解決。

### 変更・改善 (Changed)
- `ThreadSafeModelPool` による `DocumentConverter` インスタンスのキャッシュプール管理および LRU エビクション機能。
- マルチプロセスワーカー内の一時ディレクトリ作成箇所を `dir=output_dir` に限定し、パストラバーサル検証のセキュリティサンドボックスを両立。
- デフォルトの VLM プロンプトを「1〜2文で簡潔に説明」としつつ、グラフ・図表の場合は主要な数値や傾向（増減・ピーク値）を含めるスマートプロンプトに拡張し、RAG 用 Markdown の検索精度とトークン効率を両立。
- 単一画像処理時の ThreadPoolExecutor スキップによる実行オーバーヘッドの削減および並行ワーカー数の最適スロットリング (最大32)。
- 結合セルを含まないテーブルに対する GFM Markdown テーブル形式への自動フォールバック処理によるトークン消費抑制。
- Trusted Proxies パース結果のキャッシュ（`@lru_cache`）による IP 判定処理の高速化。
- `ThreadSafeModelPool` のロック粒度最適化により、重いコンバーター初期化中のスレッドブロックを防止。

### 修正 (Fixed)
- `get_concurrency_semaphore()` がアクティブな非同期イベントループに動的バインドされるよう修復し、マルチスレッド/非同期APIテスト環境での `RuntimeError` を解決。
- インメモリ Rate Limiter における期限切れタイムスタンプの定期クリーンアップによるメモリリーク防止。

## [0.1.0] - 2026-07-30

### 追加 (Added)
- Docling を利用した PDF / Word / Excel / PowerPoint 等の各種文書から RAG に最適化した Markdown への変換機能。
- CLI コマンド (`docling_converter_cli`) および FastAPI Web サーバーのエンドポイント提供。
- VLM (Ollama / Vision API) と連携した画像の自動説明文（キャプション）生成および相対パス画像リンク埋め込み。
- GPU (CUDA) 互換性チェックおよび非互換環境での CPU 自動フォールバック。
- セキュリティ機能（パス・トラバーサル防止、API キー認証、IP レート制限、Trusted Proxies 設定）。
