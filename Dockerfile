# --- ビルドターゲット引数の定義 (cpu または gpu) ---
ARG TARGET_DEVICE=gpu

# --- Stage 1: Build virtual environment ---
FROM python:3.12-slim AS builder
ARG TARGET_DEVICE

# Set environment variables for uv and optimization
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1

WORKDIR /app

# Copy the uv binary directly from official image for speed and minimal builder image size
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependencies definitions first to maximize layer caching (uv.lock is optional during initial build)
COPY pyproject.toml uv.lock* /app/

# Install project dependencies with BuildKit cache mount to preserve uv caches between builds.
# If TARGET_DEVICE is 'cpu', we remove uv.lock and dynamically modify pyproject.toml to route torch packages to the CPU-only index.
# This completely bypasses GPU packages (nvidia-* / triton) from resolution, reducing build time to a few minutes.
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$TARGET_DEVICE" = "cpu" ]; then \
        rm -f uv.lock && \
        sed -i 's/dependencies = \[/dependencies = \[\n    "torch",\n    "torchvision",/' pyproject.toml && \
        echo "" >> pyproject.toml && \
        echo "[[tool.uv.index]]" >> pyproject.toml && \
        echo 'name = "pytorch-cpu"' >> pyproject.toml && \
        echo 'url = "https://download.pytorch.org/whl/cpu"' >> pyproject.toml && \
        echo 'explicit = true' >> pyproject.toml && \
        echo "" >> pyproject.toml && \
        echo "[tool.uv.sources]" >> pyproject.toml && \
        echo 'torch = { index = "pytorch-cpu" }' >> pyproject.toml && \
        echo 'torchvision = { index = "pytorch-cpu" }' >> pyproject.toml && \
        uv sync --no-install-project --no-dev --quiet; \
    else \
        if [ -f uv.lock ]; then \
            uv sync --frozen --no-install-project --no-dev --quiet; \
        else \
            uv sync --no-install-project --no-dev --quiet; \
        fi \
    fi


# --- Stage 2: Final runtime image ---
FROM python:3.12-slim

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app/src:${PYTHONPATH}" \
    DOCLING_UPLOAD_DIR="/app/data/uploads" \
    DOCLING_OUTPUT_DIR="/app/data/output" \
    HF_HOME="/app/data/models" \
    PATH="/app/.venv/bin:${PATH}"

# Install minimal runtime system dependencies and tini
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    libxcb1 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    tini && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid 1001 -m -s /bin/bash appuser

WORKDIR /app

# Copy virtual environment and source code
COPY --from=builder /app/.venv /app/.venv
COPY ./src /app/src

# Create persistent directories with correct ownership
RUN mkdir -p /app/data/uploads /app/data/output /app/data/models \
    /app/.venv/lib/python3.12/site-packages/rapidocr/models && \
    chown -R appuser:appuser /app

# Entrypoint signals configuration
ENTRYPOINT ["/usr/bin/tini", "--"]

# Expose server port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 -O- http://localhost:8000/ || exit 1

# Default command
USER appuser
CMD ["uvicorn", "docling_lib.server:app", "--host", "0.0.0.0", "--port", "8000"]
