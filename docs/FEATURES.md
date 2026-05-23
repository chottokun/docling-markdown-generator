# Unique Features (Technical Deep Dive)

本プロジェクトは、標準的な `docling` の機能をエンタープライズ品質へと引き上げるために、以下の技術的な拡張を実装しています。

---

## 1. 堅牢なセキュリティ・レイヤー

### Path Traversal サンドボックス
入出力ディレクトリの検証には、単なる文字列マッチングではなく、OSレベルのパス解決を利用しています。
- **ロジック**: `Path(output_dir).resolve().is_relative_to(Path.cwd().resolve())`
- **効果**: 攻撃者が `../../etc/passwd` のような相対パスを指定しても、カレントディレクトリ外へのアクセスは強制的に拒絶されます。

### インジェクション攻撃の防御
- **Log Injection**: ユーザ入力由来の例外メッセージやファイル名をログに記録する際、`\n` や `\r` をスペースに置換する `sanitize_log_message` ユーティリティを全ログ出力箇所に適用。
- **YAML Frontmatter Injection**: 生成されたMarkdownのメタデータ領域において、ドキュメント名に含まれる特殊文字が悪用されるのを防ぐためのサニタイズを実装。

### API セキュリティ
- **認証**: `DOCLING_API_KEY` 環境変数が設定されている場合、`X-API-Key` ヘッダーによる強制認証が有効化されます。
- **レート制限**: FastAPIの `DependencyInjection` を活用したIPベースのレートリミッター。`RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW` で柔軟に制御可能です。

---

## 2. パフォーマンスとスケーラビリティ

### コンバーター・インスタンスのライフサイクル管理
`docling.DocumentConverter` は初期化時に複数の機械学習モデルをロードするため、リクエストごとの初期化はパフォーマンスを著しく低下させます。
- **解決策**: グローバルシングルトン `_default_pdf_converter` を導入。
- **インテリジェント・リロード**: `image_scale`, `do_ocr`, `do_formula` 等の「ヘビー」な設定項目に変更があった場合のみ、スレッドセーフにインスタンスを再構築します。

### メモリ効率の最適化
- **Streaming I/O**: 大容量ファイルのダウンロードや処理において、ファイルをメモリ上に一括ロードせず、チャンク単位で処理（httpx のストリーミング機能を活用）。ピークメモリ使用量を最大約70%削減。
- **非同期並行実行**: 重いCPU演算（変換処理）を `run_in_threadpool` に委譲することで、非同期APIサーバーのイベントループを解放。

### 動的GPU互換性検証 & セーフ・フォールバック
- **問題の背景**: 物理GPUが存在し `torch.cuda.is_available()` が `True` を返しても、GPUアーキテクチャ（Compute Capability: CC）とインストールされたPyTorchのCUDAビルドが不整合な場合（例：旧世代GPUでの実行時など）、モデルロード時に非同期のCUDAカーネルエラー（`no kernel image is available for execution`）でプロセス全体がクラッシュします。
- **動的検証技術**: サーバー起動時にGPU上で極小のテンソル演算（`torch.zeros`）を実行し、`torch.cuda.synchronize()` によって非同期にキューイングされるCUDAドライバエラーを強制同期させてトラップします。デバイスの不整合や実行時エラーが検出された場合、システムは安全に `AcceleratorDevice.CPU` へ**自動フォールバック**し、クラッシュを未然に防止します。
- **明示的制御**: 環境変数 `DOCLING_USE_GPU=False` を設定することで、不要なGPU動的検証プロセスをバイパスし、最初から強制的にCPUモードで動作させることが可能です。

### Dockerビルドの最適化とセキュア設計
- **マルチステージビルドの導入**: `ghcr.io/astral-sh/uv:latest` を用いた高速な依存関係の解決。BuildKitのキャッシュマウント (`--mount=type=cache,target=/root/.cache/uv`) を最大限に活用し、再ビルド時のパッケージダウンロードおよび同期時間を極小化。
- **高セキュア・ランタイム**: 最終ランタイムイメージにはコンパイラやパッケージマネージャなどの不要なツール・キャッシュを含めず、builderステージから必要な `/app/.venv` のみを転送することで、イメージサイズを劇的に削減（軽量化）し、コンテナの攻撃面（Attack Surface）を最小化。
- **プロセス管理の適正化**: `tini` を PID 1 として導入し、FastAPI サーバーのゾンビプロセス防止とシグナルハンドリングを適切に実行。
---

## 3. 高度な解析パイプライン (v2.x 準拠)

- **数式抽出 (LaTeX)**: `PdfPipelineOptions.do_formula_enrichment` を活用し、画像としての数式を LaTeX コードへと変換。
- **構造化テーブル**: `HTMLTableMarkdownSerializer` により、Markdown標準では表現不可能な「セルの結合」を HTML `<table>` タグとして忠実に再現。
- **OCR・レイアウト解析**: `RapidOCR` または環境に応じた OCR エンジンを選択可能。

---

## 4. 観測性とテスト環境

- **網羅的なテストスイート**: 
  - セキュリティ回帰テスト（CORS, DoS, Path Traversal）。
  - 実データを用いた E2E テスト。
- **一貫したロギング**: 全ての変換ステップにおいて構造化されたログを出力し、エラー時のトラブルシューティングを容易にしています。
