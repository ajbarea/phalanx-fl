# syntax=docker/dockerfile:1.7

# ==============================================================================
# Builder Stage: Install dependencies into a virtual environment
# ==============================================================================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# research(2026-05): pull uv from the official distroless image instead of
# `curl | sh`. The pinned `0.11.16` tag matches the current stable release;
# bump in sync with the local toolchain and the other sisters via the
# cross-repo audit (see /techne:sisters). `--compile-bytecode` on `uv sync`
# precompiles `.pyc` files at install time, trading a small image-size
# increase for faster Python cold start in the runner stage.
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /bin/

WORKDIR /app
RUN uv venv

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    UV_LINK_MODE=copy uv sync --frozen --no-dev --compile-bytecode

# ==============================================================================
# Runner Stage: Create the final production image
# ==============================================================================
FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTORCH_ALLOC_CONF=expandable_segments:True

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Run as a non-root user for security
RUN useradd -ms /bin/bash appuser
WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv ./.venv

COPY --chown=appuser:appuser intellifl/ ./intellifl/
COPY --chown=appuser:appuser config/ ./config/
COPY --chown=appuser:appuser --chmod=755 entrypoint.sh .

# Pre-create mount points so volumes inherit appuser ownership (not root)
RUN mkdir -p /app/out /app/datasets && chown -R appuser:appuser /app/out /app/datasets

USER appuser

# Validate that Python can import the package (catches missing dependencies early)
RUN python -c "import intellifl; print(f'Phalanx {intellifl.__name__} loaded successfully')"

# OCI labels for artifact identification and citation
# Includes provenance and SBOM hints for vulnerability scanning
LABEL org.opencontainers.image.title="Phalanx" \
      org.opencontainers.image.description="Federated Learning simulation framework for Byzantine-resilient aggregation research" \
      org.opencontainers.image.authors="AJ Barea <ajbareaa@gmail.com>" \
      org.opencontainers.image.source="https://github.com/ajbarea/phalanx-fl" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.created="2025-01-01" \
      org.opencontainers.image.documentation="https://ajbarea.github.io/phalanx-fl/" \
      org.opencontainers.image.vendor="Phalanx Contributors" \
      com.docker.sbom.scan-token="no-token" \
      com.docker.scout.disable="false"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD ["curl", "-f", "http://localhost:8000/api/health"]

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "intellifl.api.main:app", "--host", "0.0.0.0", "--port", "8000"]