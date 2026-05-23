# --- Stage 1: Build virtual environment ---
FROM python:3.11-slim AS builder

# Set environment variables for uv and optimization
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# Copy the uv binary directly from official image for speed and minimal builder image size
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependencies definitions first to maximize layer caching
COPY pyproject.toml uv.lock /app/

# Install project dependencies with BuildKit cache mount to preserve uv caches between builds
# We sync both production dependencies and all-extras (which includes rapidocr and layout models)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev


# --- Stage 2: Final runtime image ---
FROM python:3.11-slim

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
COPY ./tests /app/tests

# Create persistent directories with correct ownership
RUN mkdir -p /app/data/uploads /app/data/output /app/data/models \
    /app/.venv/lib/python3.11/site-packages/rapidocr/models && \
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
