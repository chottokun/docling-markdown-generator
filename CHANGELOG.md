# CHANGELOG

このプロジェクトのすべての顕著な変更点は、このファイルに記録されます。

フォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) に基づいており、
このプロジェクトは [Semantic Versioning](https://semver.org/lang/ja/) に準拠します。

## [Unreleased]

### 追加 (Added)
- `ThreadSafeModelPool` による `DocumentConverter` インスタンスのキャッシュプール管理および LRU エビクション機能。
- マルチスレッド並行アクセス時の `ThreadSafeModelPool` スレッドセーフ性テストおよび不正テーブルデータに対する堅牢性テスト。

### 変更・改善 (Changed)
- デフォルトの VLM プロンプトを「1〜2文程度で簡潔に説明」する要約指向のプロンプトに変更し、RAG 用 Markdown のトークン節約および可読性を向上。
- 単一画像処理時の ThreadPoolExecutor スキップによる実行オーバーヘッドの削減および並行ワーカー数の最適スロットリング (最大32)。
- 結合セルを含まないテーブルに対する GFM Markdown テーブル形式への自動フォールバック処理によるトークン消費抑制。
- Trusted Proxies パース結果のキャッシュ（`@lru_cache`）による IP 判定処理の高速化。
- `ThreadSafeModelPool` のロック粒度最適化により、重いコンバーター初期化中のスレッドブロックを防止。

### 修正 (Fixed)
- インメモリ Rate Limiter における期限切れタイムスタンプの定期クリーンアップによるメモリリーク防止。

## [0.1.0] - 2026-07-30

### 追加 (Added)
- Docling を利用した PDF / Word / Excel / PowerPoint 等の各種文書から RAG に最適化した Markdown への変換機能。
- CLI コマンド (`docling_converter_cli`) および FastAPI Web サーバーのエンドポイント提供。
- VLM (Ollama / Vision API) と連携した画像の自動説明文（キャプション）生成および相対パス画像リンク埋め込み。
- GPU (CUDA) 互換性チェックおよび非互換環境での CPU 自動フォールバック。
- セキュリティ機能（パス・トラバーサル防止、API キー認証、IP レート制限、Trusted Proxies 設定）。
