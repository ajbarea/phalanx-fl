# syntax=docker/dockerfile:1.7

# ==============================================================================
# Zensical docs server
# ==============================================================================
#
# research(2026-05): bakes zensical into the image at build time via uv,
# replacing the previous `pip install --quiet zensical` that ran on every
# container start. Trade-off: a one-time ~15s `docker compose build` cost
# in exchange for ~5s saved on every `make docs` / `up` / `restart` cycle
# plus version-pin reproducibility (the inline pip install pulled the
# latest 0.0.x release on every restart, which was a moving target).
#
# Zensical is pre-1.0 (0.0.x); pinning to a patch keeps cross-sister drift
# visible to /techne:sisters cron audits. Bump in lockstep with the other
# Zensical-powered sisters (techne, kourai-khryseai, vFL, ldqis-website).

FROM python:3.12-slim AS docs

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# UV_SYSTEM_PYTHON=1 tells uv to install into the system Python rather than
# spinning up a separate venv — this image is a single-purpose docs server
# so the extra indirection doesn't earn its weight.
ENV UV_SYSTEM_PYTHON=1

RUN uv pip install --no-cache-dir --compile-bytecode "zensical==0.0.32"

EXPOSE 8000

CMD ["zensical", "serve", "--dev-addr", "0.0.0.0:8000"]
