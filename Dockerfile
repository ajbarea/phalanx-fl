# syntax=docker/dockerfile:1

# ==============================================================================
# Builder Stage: Install dependencies into a virtual environment
# ==============================================================================
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build-time dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create a virtual environment
WORKDIR /app
RUN uv venv

# Install Python dependencies into the virtual environment with cache mount
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ==============================================================================
# Runner Stage: Create the final production image
# ==============================================================================
FROM python:3.11-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Point to the virtual environment
    VIRTUAL_ENV=/app/.venv \
    # Add the venv's bin directory to the PATH
    PATH="/app/.venv/bin:$PATH" \
    PYTORCH_ALLOC_CONF=expandable_segments:True

# Install only essential runtime system dependencies
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

# Copy the virtual environment from the builder stage
COPY --from=builder --chown=appuser:appuser /app/.venv ./.venv

# Copy application code with the appuser ownership
COPY --chown=appuser:appuser intellifl/ ./intellifl/
COPY --chown=appuser:appuser config/ ./config/
COPY --chown=appuser:appuser --chmod=755 entrypoint.sh .

# Create and set ownership for directories that will be mounted as volumes
RUN mkdir -p /app/out /app/datasets && chown -R appuser:appuser /app/out /app/datasets

# Switch to the non-root user
USER appuser

# Validate that Python can import the package (catches missing dependencies early)
RUN python -c "import intellifl; print(f'IntelliFL {intellifl.__name__} loaded successfully')"

# OCI labels for artifact identification and citation
LABEL org.opencontainers.image.title="IntelliFL"
LABEL org.opencontainers.image.description="Federated Learning simulation framework for Byzantine-resilient aggregation research"
LABEL org.opencontainers.image.authors="AJ Barea <ajbareaa@gmail.com>"
LABEL org.opencontainers.image.source="https://github.com/dmitrykoro/fl-execution-framework/tree/aj-ux-enhancements"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.created="2025-01-01"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD ["curl", "-f", "http://localhost:8000/api/health"]

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "intellifl.api.main:app", "--host", "0.0.0.0", "--port", "8000"]