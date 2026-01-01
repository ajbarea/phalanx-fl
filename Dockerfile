# Research: Reproducible container guidelines (Rule 4: Version Control)
# https://doi.org/10.1371/journal.pcbi.1008316

# PyTorch base with CUDA (auto-detects GPU at runtime via torch.cuda.is_available)
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

# OCI labels for artifact identification and citation
LABEL org.opencontainers.image.title="IntelliFL"
LABEL org.opencontainers.image.description="Federated Learning simulation framework for Byzantine-resilient aggregation research"
LABEL org.opencontainers.image.authors="AJ Barea <ajbareaa@gmail.com>"
LABEL org.opencontainers.image.source="https://github.com/dmitrykoro/fl-execution-framework/tree/aj-ux-enhancements"
LABEL org.opencontainers.image.version="1.0.0"
# LABEL org.opencontainers.image.url="https://doi.org/10.5281/zenodo.XXXXXXX"  # Add after Zenodo upload
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.created="2025-01-01"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CUDA_VISIBLE_DEVICES="" \
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

WORKDIR /app

# curl for healthcheck, git for model downloads
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Requirements first for layer caching (PyTorch already in base image)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/

# Entrypoint auto-downloads datasets on first run
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Mounted at runtime for data persistence
RUN mkdir -p /app/out /app/datasets

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
