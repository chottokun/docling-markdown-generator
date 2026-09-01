# デプロイメント・ガイド (Deployment Guide)

本サーバーを本番環境やコンテナ環境（Docker / Kubernetes 等）で安定運用するためのガイドです。

---

## 1. 環境変数による設定一覧

すべての設定は環境変数（または `.env` ファイル）で制御できます。

### 1.1 セキュリティ & サーバー基本設定
| 変数名 | デフォルト値 | 説明 |
| :--- | :--- | :--- |
| `DOCLING_API_KEY` | *(未設定)* | 設定した場合、全エンドポイントで `X-API-Key` ヘッダーによる認証が有効になります。 |
| `DOCLING_CORS_ORIGINS` | *(空)* | 許可するCORSオリジンのカンマ区切りリスト（例: `http://localhost:3000,https://example.com`）。 |
| `DOCLING_MAX_UPLOAD_SIZE` | `20971520` | 最大アップロードサイズ（バイト単位）。デフォルトは20MB。 |
| `DOCLING_RATE_LIMIT_REQUESTS`| `5` | IPアドレスごとの最大許可リクエスト数（レートリミット）。 |
| `DOCLING_RATE_LIMIT_WINDOW`  | `60` | レートリミットの計測ウィンドウ（秒数）。 |
| `DOCLING_TRUSTED_PROXIES`    | *(空)* | 信頼するリバースプロキシのIP/CIDR（IPスプーフィング対策用）。 |
| `DOCLING_MAX_WORKERS`        | `2` | 独立した子プロセス（ProcessPoolExecutor）のワーカープロセス数。 |
| `DOCLING_UPLOAD_DIR`         | `uploads` | アップロードされたファイルの一時保存先（コンテナ内: `/app/data/uploads`）。 |
| `DOCLING_OUTPUT_DIR`         | `output` | 変換済みファイルの保存先（コンテナ内: `/app/data/output`）。 |

### 1.2 Docling 変換パイプライン & ハードウェア設定
| 変数名 | デフォルト値 | 説明 |
| :--- | :--- | :--- |
| `DOCLING_USE_GPU` | `True` | GPU（CUDA）アクセラレーションの利用制御。`False` で強制CPUモード。非対応GPU環境では自動でCPUにフォールバックします。 |
| `DOCLING_NUM_THREADS` | `4` | CPU/GPU前処理等で使用される演算スレッド数。 |
| `DOCLING_CUDA_FLASH_ATTENTION` | `False` | サポートされているハイエンドGPUでFlashAttention2を有効化（推論高速化・VRAM節約）。 |
| `DOCLING_DO_OCR` | `True` | OCR（光学文字認識）を有効にする。 |
| `DOCLING_DO_FORMULA` | `True` | 数式（LaTeX）の抽出・認識を有効にする。 |
| `DOCLING_DO_CHART` | `False` | 図表（チャート/グラフ）の抽出と解析を有効にする。 |
| `DOCLING_DO_CODE` | `False` | ソースコードブロックの高度な認識を有効にする。 |
| `DOCLING_TABLE_FORMAT` | `html` | テーブルの出力形式（`html`, `markdown`, `csv`, `tsv`）。 |
| `IMAGE_RESOLUTION_SCALE` | `2.0` | 抽出される画像の解像度倍率（大きいほど高画質）。 |
| `DOCLING_INCLUDE_PAGE_BREAKS` | `False` | Markdown内に `<!-- PAGE_BREAK: Page N -->` を出力（RAGチャンキング用）。 |
| `DOCLING_INCLUDE_KV_EXTRACTION` | `False` | YAMLヘッダー部に重要情報（KV抽出）を出力。 |
| `DOCLING_MATH_INLINE_DELIM` | `auto` | インライン数式のデリミタ（例: `$`, `\(`, `auto`）。 |
| `DOCLING_MATH_BLOCK_DELIM` | `auto` | ブロック数式のデリミタ（例: `$$`, `\[`, `auto`）。 |
| `DOCLING_MATH_BLOCK_NEWLINE` | `auto` | ブロック数式前後の改行制御（`auto`, `true`, `false`）。 |

### 1.3 VLM (Vision Language Model) / LLM 画像キャプション生成設定
| 変数名 | デフォルト値 | 説明 |
| :--- | :--- | :--- |
| `DOCLING_VLM_ENABLED` | `False` | **【重要】デフォルト無効**。`True` に設定した場合のみ画像・図表のVLMキャプション生成を実行。 |
| `DOCLING_VLM_PROVIDER` | `ollama` | 利用するプロバイダ（`ollama`, `openai`, `vllm`, `llama.cpp`, `google`, `gemini`, `anthropic`）。 |
| `DOCLING_VLM_API_KEY` | *(空)* | 各種プロバイダのAPIキー（OpenAI / Anthropic / Google / 認証付きOpenAI互換サーバー）。 |
| `DOCLING_VLM_MODEL` | `qwen2-vl:2b` | 利用するモデル名（例: `gpt-4o-mini`, `gemini-1.5-flash`, `qwen2-vl:2b` 等）。 |
| `DOCLING_VLM_ENDPOINT` | `http://localhost:11434` | APIエンドポイントURL。 |
| `DOCLING_VLM_PROMPT` | （画像説明指示文） | VLMへ送信するキャプション生成用日本語プロンプト。 |
| `DOCLING_VLM_MAX_CONCURRENT` | `5` | 同時リクエスト数のセマフォ流量制限値。 |

---

## 2. VLM プロバイダ別設定例

### 2.1 ホストPC上の Ollama
ホストマシンや別サーバーで起動している Ollama を利用する場合の設定です。APIキーは不要（空欄）です。
```bash
DOCLING_VLM_ENABLED=True
DOCLING_VLM_PROVIDER=ollama
DOCLING_VLM_MODEL=qwen2-vl:2b
DOCLING_VLM_API_KEY=  # APIキー不要（空欄）
# Base URL / エンドポイント:
# - DockerコンテナからホストPCのOllamaへ接続する場合:
DOCLING_VLM_ENDPOINT=http://host.docker.internal:11434
# - ローカルPython (CLI等) から直接接続する場合:
# DOCLING_VLM_ENDPOINT=http://localhost:11434
```

### 2.2 ローカルの OpenAI 互換推論サーバー（vLLM / llama.cpp / LM Studio / LocalAI / LiteLLM 等）
ローカルPCや社内サーバーの OpenAI 互換 API を利用する場合の設定です。認証不要な環境ではAPIキーは空欄で構いません。
```bash
DOCLING_VLM_ENABLED=True
DOCLING_VLM_PROVIDER=openai  # または vllm / llama.cpp
DOCLING_VLM_MODEL=Qwen/Qwen2-VL-7B-Instruct
DOCLING_VLM_API_KEY=  # 認証不要な場合は空欄（認証付きの場合はキーを指定）
# Base URL / エンドポイント:
# - Dockerコンテナからアクセスする場合:
DOCLING_VLM_ENDPOINT=http://host.docker.internal:8000/v1
# （LM Studio の場合は http://host.docker.internal:1234/v1 など）
# - ローカルPythonからアクセスする場合:
# DOCLING_VLM_ENDPOINT=http://localhost:8000/v1
```

### 2.3 クラウド OpenAI (GPT-4o mini 等)
```bash
DOCLING_VLM_ENABLED=True
DOCLING_VLM_PROVIDER=openai
DOCLING_VLM_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx
DOCLING_VLM_MODEL=gpt-4o-mini
DOCLING_VLM_ENDPOINT=https://api.openai.com/v1
```

### 2.4 Google Gemini (gemini-1.5-flash 等)
```bash
DOCLING_VLM_ENABLED=True
DOCLING_VLM_PROVIDER=google
DOCLING_VLM_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxx
DOCLING_VLM_MODEL=gemini-1.5-flash
DOCLING_VLM_ENDPOINT=https://generativelanguage.googleapis.com
```

### 2.5 Anthropic Claude (Claude 3.5 Sonnet 等)
```bash
DOCLING_VLM_ENABLED=True
DOCLING_VLM_PROVIDER=anthropic
DOCLING_VLM_API_KEY=sk-ant-api03-xxxxxxxxxxxx
DOCLING_VLM_MODEL=claude-3-5-sonnet-20241022
DOCLING_VLM_ENDPOINT=https://api.anthropic.com
```

---

## 3. Docker Compose による運用

本リポジトリは `docling-server` 単独のコンテナ構成となっており、Ollama等の外部モデルサーバーは内包していません。

### 3.1 起動手順
```bash
# 設定ファイルの準備
cp .env.example .env

# 起動（バックグラウンド実行）
docker compose up -d --build
```
- APIサーバー: `http://localhost:8090` (コンテナ内ポート 8000 をホストの 8090 へ転送)

### 3.2 CPU のみでビルド・起動したい場合
Dockerfile のビルド引数 `TARGET_DEVICE=cpu` を指定します。
```bash
docker build --build-arg TARGET_DEVICE=cpu -t docling-server-cpu .
```

---

## 4. ヘルスチェックとログ監視

### ヘルスチェック
サーバーが正常にリクエストを受け付けられるか確認します。
```bash
curl -f http://localhost:8090/ || exit 1
```

### ログ監視
```bash
docker compose logs -f docling-server
```

---

## 5. ストレージ管理

変換されたファイルは `DOCLING_OUTPUT_DIR`（コンテナ内 `/app/data/output`）に蓄積されます。
定期的なクリーンアップ（例: 24時間以上経過したディレクトリの削除）を行う cron ジョブやサイドカーコンテナの運用を推奨します。

```bash
# 24時間以上経過した出力ファイルを削除する例
find /path/to/data/output/* -type d -ctime +1 -exec rm -rf {} +
```

---

## 6. 初回起動時のモデルダウンロードと永続化

### 6.1 ダウンロードのタイミング（オンデマンド取得）
Docling のレイアウト解析モデルや OCR モデル等は、**初めて変換リクエスト（`POST /convert/` または CLI）を実行したタイミング**で、Hugging Face Hub 等から自動的にダウンロードされます。
- 初回変換時のみダウンロード処理（数百MB〜約1GB）が発生するため、初回の応答には数十秒〜1分程度かかります。
- 2回目以降のリクエストは、キャッシュされたモデルがロードされるため即座に高速処理されます。

### 6.2 Docker ボリュームによるモデルの永続化
- コンテナ環境では環境変数 `HF_HOME=/app/data/models` が設定されています。
- `docker-compose.yml` において名前付きボリューム `docling_data:/app/data` をマウントしているため、一度ダウンロードされたモデルファイルはホスト上の Docker ボリュームに永続化されます。
- コンテナの再起動（`docker compose restart`）や再ビルド（`docker compose up --build`）を行っても、ボリュームが存在する限り**再ダウンロードは発生しません**。

### 6.3 デプロイ時の事前ウォームアップ（任意）
本番環境等で、ユーザーからの初弾リクエストでのダウンロード待ちを回避したい場合は、コンテナ起動直後に以下のコマンドを実行して事前にモデルをキャッシュしておくことができます。

```bash
# コンテナ内で Docling のモデル事前ロード（ウォームアップ）を実行
docker compose exec docling-server python -c "from docling.document_converter import DocumentConverter; DocumentConverter()"
```
