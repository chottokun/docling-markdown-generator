# Unique Features (Technical Deep Dive)

本プロジェクトは、標準的な `docling` の機能をエンタープライズ品質へと引き上げるために、以下の技術的な拡張を実装しています。

---

## 1. 堅牢なセキュリティ・レイヤー

### Path Traversal サンドboxes
入出力ディレクトリの検証には、単なる文字列マッチングではなく、OSレベルのパス解決を利用しています。
- **ロジック**: `Path(output_dir).resolve().is_relative_to(Path.cwd().resolve())`
- **効果**: 攻撃者が `../../etc/passwd` のような相対パスを指定しても、カレントディレクトリ外へのアクセスは強制的に拒絶されます。
- **ワーカー安全領域**: マルチプロセスワーカー処理時においても、一時ディレクトリを `output_dir` 内に限定生成し、サンドボックス保護を厳格に維持します。

### インジェクション攻撃の防御
- **Log Injection**: ユーザ入力由来の例外メッセージやファイル名をログに記録する際、`\n` や `\r` をスペースに置換する `sanitize_log_message` ユーティリティを全ログ出力箇所に適用。
- **YAML Frontmatter Injection**: 生成されたMarkdownのメタデータ領域において、ドキュメント名に含まれる特殊文字が悪用されるのを防ぐためのサニタイズを実装。

### API セキュリティ
- **認証**: `DOCLING_API_KEY` 環境変数が設定されている場合、`X-API-Key` ヘッダーによる強制認証が有効化されます。
- **レート制限**: FastAPIの `DependencyInjection` を活用したIPベースのレートリミッター。`RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW` で制御し、10分周期での定期的なメモリクリーンアップによりリークを防ぎます。

---

## 2. パフォーマンスとスケーラビリティ

### マルチプロセス並列化エンジン (ProcessPoolExecutor)
PyTorch や C++ 拡張を含む Docling の重い変換処理は、Python の GIL (Global Interpreter Lock) によりスレッド並列でのパフォーマンスが頭打ちになる課題がありました。
- **解決策**: FastAPI 内から `ProcessPoolExecutor(mp_context='spawn')` を用いた完全なマルチプロセス並列実行へ移行。
- **効果**: API サーバーのイベントループが CPU 重負荷によりブロックされる問題を根本解決し、大容量ドキュメントの複数同時変換時にも最高レベルの応答性を維持します。

### メモリ適応型動的セマフォ制御 (`get_dynamic_semaphore_limit`)
- **問題**: 同時リクエストが集中した際、プロセスごとのモデル消費メモリ（約1.5GB〜4GB）により OOM (Out of Memory) キラーが起動し、サーバーがクラッシュする危険がありました。
- **動的制御**: `psutil.virtual_memory()` を利用して空き RAM 容量から安全な並行実行数を動的に計算し、`asyncio.Semaphore` でリクエストを並行制御。
- **イベントループ追跡**: アクティブな非同期イベントループに動的バインドすることで、マルチスレッド/非同期APIテスト環境でのループ非互換エラーを完全に防ぎます。

### コンバーター・インスタンスの LRU モデルキャッシュ (`ThreadSafeModelPool`)
`docling.DocumentConverter` は初期化時に複数の機械学習モデルをロードするため、リクエストごとの初期化はパフォーマンスを著しく低下させます。
- **解決策**: スレッドセーフな `ThreadSafeModelPool` (LRU キャッシュ) を導入。
- **インテリジェント・リロード**: `image_scale`, `do_ocr`, `do_formula` 等の「ヘビー」な設定項目に変更があった場合のみ、新しいインスタンスを自動生成・再利用します。

### メモリ効率の最適化
- **Streaming I/O & Non-blocking Save (`aiofiles`)**: アップロードファイルを一括メモリロードせず、1MB 単位の非同期ストリーミングでディスクへ一時保存。
- **VLM Prefetching**: ドキュメント内画像への VLM キャプション生成を ThreadPool で非同期並列プレフェッチ。

### 動的GPU互換性検証 & セーフ・フォールバック
- **問題の背景**: 物理GPUが存在し `torch.cuda.is_available()` が `True` を返しても、GPUアーキテクチャ（Compute Capability: CC）とインストールされたPyTorchのCUDAビルドが不整合な場合（例：旧世代GPUでの実行時など）、モデルロード時に非同期のCUDAカーネルエラーでプロセス全体がクラッシュします。
- **動的検証技術**: `is_cuda_compatible()` により Compute Capability >= 7.5 を検証し、かつ GPU 上での極小テンソル演算結果を同期トラップ。不整合検出時は安全に `AcceleratorDevice.CPU` へ**自動フォールバック**します。詳細およびGPU環境でのテスト手順は [GPU_TESTING.md](GPU_TESTING.md) を参照してください。

---

## 3. 高度な解析パイプライン (v2.x 準拠)

- **数式抽出 (LaTeX)**: `PdfPipelineOptions.do_formula_enrichment` を活用し、画像としての数式を LaTeX コードへと変換。
- **柔軟な画像タグテンプレートと資産抽出 (`EnhancedDoclingConverter`)**: デフォルトで最高レベルの互換性を持つ CommonMark 形式 (`![image](path)`) の画像リンクを出力しつつ、オプション指定で Obsidian 形式 (`![[...]]`) への即時切替および指定ディレクトリ (`assets_dir`) への画像自動保存に対応。
- **構造化テーブル**: `HTMLTableMarkdownSerializer` により、Markdown標準では表現不可能な「セルの結合」を HTML `<table>` タグとして忠実に再現。
- **OCR・レイアウト解析**: `RapidOCR` または環境に応じた OCR エンジンを選択可能。

---

## 4. 観測性とテスト環境

- **網羅的なテストスイート**: 
  - セキュリティ回帰テスト（CORS, DoS, Path Traversal）。
  - マルチプロセス並列化および負荷ストレステスト。
  - 実データを用いた E2E テスト。
- **一貫したロギング**: 全ての変換ステップにおいて構造化されたログを出力し、エラー時のトラブルシューティングを容易にしています。
