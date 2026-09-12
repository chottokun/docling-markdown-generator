# Deployment Guide

Language: [English](DEPLOYMENT.md) | [日本語](../DEPLOYMENT.md)

This guide covers stable production and containerized (Docker / Kubernetes) deployment of the Docling Markdown Conversion Server.

---

## 1. Configuration via Environment Variables

All settings can be configured using environment variables or a `.env` file.

### 1.1 Security & Core Server Settings
| Variable Name | Default Value | Description |
| :--- | :--- | :--- |
| `DOCLING_API_KEY` | *(Unset)* | When set, enables mandatory authentication via `X-API-Key` header for all endpoints. |
| `DOCLING_CORS_ORIGINS` | *(Empty)* | Comma-separated list of allowed CORS origins (e.g. `http://localhost:3000,https://example.com`). |
| `DOCLING_MAX_UPLOAD_SIZE` | `20971520` | Maximum upload size in bytes (default: 20MB). |
| `DOCLING_RATE_LIMIT_REQUESTS`| `5` | Maximum allowed requests per IP address within window. |
| `DOCLING_RATE_LIMIT_WINDOW`  | `60` | Rate limiting evaluation window in seconds. |
| `DOCLING_TRUSTED_PROXIES`    | *(Empty)* | Trusted reverse proxy IPs/CIDRs for IP spoofing mitigation. |
| `DOCLING_MAX_WORKERS`        | `2` | Number of worker processes in `ProcessPoolExecutor`. |
| `DOCLING_UPLOAD_DIR`         | `uploads` | Directory for uploaded files (In container: `/app/data/uploads`). |
| `DOCLING_OUTPUT_DIR`         | `output` | Directory for converted output files (In container: `/app/data/output`). |
| `DOCLING_ALLOW_ABSOLUTE_OUTPUT_DIR` | `False` | Whether to allow absolute output directories outside CWD (disabled by default to prevent path traversal and protect system directories). |

### 1.2 Docling Conversion Pipeline & Hardware Settings
| Variable Name | Default Value | Description |
| :--- | :--- | :--- |
| `DOCLING_USE_GPU` | `True` | GPU (CUDA) acceleration control. Set `False` to force CPU mode. Automatically falls back to CPU if unsupported GPU detected. |
| `DOCLING_NUM_THREADS` | `4` | CPU thread count used during processing. |
| `DOCLING_CUDA_FLASH_ATTENTION` | `False` | Enables FlashAttention2 on supported high-end GPUs for inference speedup and VRAM savings. |
| `DOCLING_DO_OCR` | `True` | Enables Optical Character Recognition (OCR). |
| `DOCLING_DO_FORMULA` | `True` | Enables formula (LaTeX) extraction and recognition. |
| `DOCLING_DO_CHART` | `False` | Enables chart and diagram analysis. |
| `DOCLING_DO_CODE` | `False` | Enables advanced source code block recognition. |
| `DOCLING_TABLE_FORMAT` | `html` | Output table format (`html`, `markdown`, `csv`, `tsv`). |
| `IMAGE_RESOLUTION_SCALE` | `2.0` | Resolution scale factor for extracted images (higher = higher quality). |
| `DOCLING_INCLUDE_PAGE_BREAKS` | `False` | Outputs `<!-- PAGE_BREAK: Page N -->` markers in Markdown for RAG chunking. |
| `DOCLING_INCLUDE_KV_EXTRACTION` | `False` | Outputs key-value extractions in frontmatter. |
| `DOCLING_MATH_INLINE_DELIM` | `auto` | Inline math delimiter (e.g. `$`, `\(`, `auto`). |
| `DOCLING_MATH_BLOCK_DELIM` | `auto` | Block math delimiter (e.g. `$$`, `\[`, `auto`). |
| `DOCLING_MATH_BLOCK_NEWLINE` | `auto` | Inner newline control for block formulas (`auto`, `true`, `false`). |

### 1.3 VLM (Vision Language Model) / Image Caption Settings
| Variable Name | Default Value | Description |
| :--- | :--- | :--- |
| `DOCLING_VLM_ENABLED` | `False` | **Disabled by default**. Set `True` to enable VLM captioning for figures and images. |
| `DOCLING_VLM_PROVIDER` | `ollama` | Provider backend (`ollama`, `openai`, `vllm`, `llama.cpp`, `google`, `gemini`, `anthropic`). |
| `DOCLING_VLM_API_KEY` | *(Empty)* | API Key for authenticated providers (OpenAI / Anthropic / Google / OpenAI-compatible servers). |
| `DOCLING_VLM_MODEL` | `qwen2-vl:2b` | Model name (e.g., `gpt-4o-mini`, `gemini-1.5-flash`, `qwen2-vl:2b`). |
| `DOCLING_VLM_ENDPOINT` | `http://localhost:11434` | API endpoint URL. |
| `DOCLING_VLM_PROMPT` | (Caption prompt) | Image description prompt sent to VLM. |
| `DOCLING_VLM_MAX_CONCURRENT` | `5` | Semaphore concurrency limit for VLM requests. |

---

## 2. VLM Configuration Examples by Provider

### 2.1 Host-based Ollama
Configuration when using Ollama running on host machine or external server. No API key needed.
```bash
DOCLING_VLM_ENABLED=True
DOCLING_VLM_PROVIDER=ollama
DOCLING_VLM_MODEL=qwen2-vl:2b
DOCLING_VLM_API_KEY=  # Not needed (leave blank)
# Endpoint URL:
# - From Docker container connecting to host Ollama:
DOCLING_VLM_ENDPOINT=http://host.docker.internal:11434
# - From local Python (CLI):
# DOCLING_VLM_ENDPOINT=http://localhost:11434
```

### 2.2 Local OpenAI-Compatible Server (vLLM / llama.cpp / LM Studio / LocalAI / LiteLLM)
```bash
DOCLING_VLM_ENABLED=True
DOCLING_VLM_PROVIDER=openai  # or vllm / llama.cpp
DOCLING_VLM_MODEL=Qwen/Qwen2-VL-7B-Instruct
DOCLING_VLM_API_KEY=  # Leave blank if unauthenticated
# Endpoint URL:
# - From Docker container:
DOCLING_VLM_ENDPOINT=http://host.docker.internal:8000/v1
```

### 2.3 Cloud OpenAI (GPT-4o mini, etc.)
```bash
DOCLING_VLM_ENABLED=True
DOCLING_VLM_PROVIDER=openai
DOCLING_VLM_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx
DOCLING_VLM_MODEL=gpt-4o-mini
DOCLING_VLM_ENDPOINT=https://api.openai.com/v1
```

### 2.4 Google Gemini (gemini-1.5-flash, etc.)
```bash
DOCLING_VLM_ENABLED=True
DOCLING_VLM_PROVIDER=google
DOCLING_VLM_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxx
DOCLING_VLM_MODEL=gemini-1.5-flash
DOCLING_VLM_ENDPOINT=https://generativelanguage.googleapis.com
```

### 2.5 Anthropic Claude (Claude 3.5 Sonnet, etc.)
```bash
DOCLING_VLM_ENABLED=True
DOCLING_VLM_PROVIDER=anthropic
DOCLING_VLM_API_KEY=sk-ant-api03-xxxxxxxxxxxx
DOCLING_VLM_MODEL=claude-3-5-sonnet-20241022
DOCLING_VLM_ENDPOINT=https://api.anthropic.com
```

---

## 3. Deployment with Docker Compose

```bash
# Prepare environment file
cp .env.example .env

# Build & Start Container
docker compose up -d --build
```
- API Server: `http://localhost:8090`

### CPU-Only Docker Build
```bash
docker build --build-arg TARGET_DEVICE=cpu -t docling-server-cpu .
```

---

## 4. Health Check & Logs

### Health Check
```bash
curl -f http://localhost:8090/ || exit 1
```

### View Logs
```bash
docker compose logs -f docling-server
```

---

## 5. Storage Management

Converted files accumulate in `DOCLING_OUTPUT_DIR` (`/app/data/output` in container).
Configure periodic cleanup jobs (e.g. deleting directories older than 24 hours):

```bash
find /path/to/data/output/* -type d -ctime +1 -exec rm -rf {} +
```

---

## 6. Pre-downloading Models & Host Cache Persistence

### 6.1 Host-side Cache (`.cache_models`)
Pre-downloading models to `.cache_models/` on the host persists models across container restarts and local test runs:

```bash
# Download standard models
uv run python scripts/download_models.py

# Download all available models
uv run python scripts/download_models.py --all
```

### 6.2 Docker Volume Mounting
- `docker-compose.yml` mounts `./.cache_models` on host to `/app/data/models` inside the container.
- `DOCLING_ARTIFACTS_PATH=/app/data/models`, `HF_HOME=/app/data/models`, and `DOCLING_CACHE_DIR=/app/data` ensure offline instant startup without re-downloading.

### 6.3 LibreOffice & CJK Fonts
- The Docker image includes `libreoffice-nogui`, `fonts-noto-cjk`, and `fonts-liberation`.
- Enables high-resolution vector image (EMF/WMF) rasterization and chart rendering in Office documents without font substitution or garbled Japanese text.

---

## 7. Prometheus Monitoring

The server exposes Prometheus metrics at `/metrics`.

### Prometheus Scraping Configuration (`prometheus.yml`)
```yaml
scrape_configs:
  - job_name: 'docling-markdown-generator'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8090']
```

---

## 8. Container E2E Verification

Run the included E2E verification script against the running container:

```bash
uv run python tests/e2e_docker_check.py
```

---

## 9. Troubleshooting

| Symptom | Cause | Resolution |
| :--- | :--- | :--- |
| `GPU compute capability is less than required 7.5. Falling back to CPU.` | Older GPU detected | Expected behavior; automatically falls back to CPU mode safely. |
| `Payload Too Large` (413) | File exceeds maximum upload size | Increase `DOCLING_MAX_UPLOAD_SIZE` in `.env`. |
| `Too Many Requests` (429) | Rate limit exceeded | Increase `DOCLING_RATE_LIMIT_REQUESTS` or adjust client retry interval. |
