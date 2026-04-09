# :material-rocket-launch: Getting Started

## Option A — Docker Compose :material-star:{ title="Recommended" }

The fastest way to run InteFL. Docker Compose brings up the full stack — API, frontend, Redis, Celery worker, documentation site, and optional Celery monitor — with a single command. No Python environment or Node.js install required.

!!! info "Prerequisites"

    - [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Compose)
    - [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) *(optional — for GPU support)*

=== ":material-server-network: Production"

    ```bash title="Start in production mode"
    docker compose -f docker-compose.yml up -d
    ```

    | Service | URL | Description |
    |---|---|---|
    | :material-react: Frontend UI | `http://localhost:80` | React dashboard (nginx) |
    | :material-api: Backend API | `http://localhost:8000` | FastAPI + Swagger docs at `/docs` |
    | :material-book-open-variant: Documentation | `http://localhost:8080` | Zensical docs site |

=== ":material-code-braces: Development"

    ```bash title="Start in development mode"
    uv run intellifl-dev dev
    ```

    > Runs `docker compose up` through the project's cross-platform developer CLI and automatically applies `docker-compose.override.yml`

    | Service | URL | Description |
    |---|---|---|
    | :material-react: Frontend UI | `http://localhost:5173` | Vite dev server with hot reload |
    | :material-api: Backend API | `http://localhost:8000` | FastAPI with `--reload` |
    | :material-flower-tulip: Celery monitor | `http://localhost:5555` | Flower task queue dashboard |
    | :material-book-open-variant: Documentation | `http://localhost:8080` | Zensical docs site |

**Common commands:**

```bash title="Useful local commands"
uv run intellifl-dev dev         # Start all services in dev mode (hot reload, Celery monitoring)
uv run intellifl-dev dev-down    # Stop all services
docker compose logs -f           # Tail logs from all services
docker compose logs -f api       # Tail logs from the API service only
```

!!! example "Run a simulation directly via CLI inside the container"

    ```bash
    docker compose run --rm api python -m intellifl.simulation_runner <config.json>
    ```

### :material-key-variant: Environment setup

The project ships a `.env.example` with sensible defaults. Copy it to `.env` before your first run:

```bash title="Create .env file (macOS / Linux / Git Bash)"
cp .env.example .env
```

```powershell title="Create .env file (PowerShell)"
Copy-Item .env.example .env
```

!!! warning ".env is gitignored"

    `.env` is never committed — safe for secrets like `HF_TOKEN`. Edit it to override any of the variables below:

| Variable | Default | Description |
|---|---|---|
| `API_PORT` | `8000` | Host port for the API |
| `FRONTEND_PORT` | `80` | Host port for the frontend (production) |
| `FRONTEND_DEV_PORT` | `5173` | Host port for Vite dev server (development only) |
| `DOCS_PORT` | `8080` | Host port for the documentation site |
| `CELERY_CONCURRENCY` | `1` | Number of parallel Celery workers |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Redis broker URL for Celery |
| `CELERY_RESULT_BACKEND_URL` | `redis://redis:6379/1` | Redis backend URL for Celery results |
| `HF_HOME` | `./cache/huggingface` | HuggingFace cache directory |
| `HF_TOKEN` | *(empty)* | [HuggingFace access token](https://huggingface.co/settings/tokens) (needed for gated datasets) |
| `VITE_API_PROXY_TARGET` | `http://api:8000` | API proxy target for Vite dev server |
| `VITE_DOCS_PROXY_TARGET` | `http://docs:8000` | Docs proxy target for Vite dev server |
| `VITE_DOCS_PORT` | `8080` | Docs port for Vite dev server (must match `DOCS_PORT`) |

**Persistent volumes:**

| Volume | Description |
|---|---|
| `./out` | Simulation outputs (results, CSVs, plots) — persists across container restarts |
| `./datasets` | Datasets — auto-downloaded on first run, persists across restarts |
| `./config` | Strategy configs (read-only inside container) |
| `redis-data` | Redis task queue state — persists across restarts |

---

## Option B — Local development

Preferred if you are actively editing the codebase. Installs dependencies locally for IDE support, linting, and direct CLI usage. Services still run via Docker Compose.

!!! info "Prerequisites"

    | Requirement | Version |
    |---|---|
    | :material-package-variant-closed: uv | 0.5.3+ |
    | :material-language-python: CPython | 3.11 – 3.13 (uv-managed preferred) |
    | :material-nodejs: Node.js | 20+ |
    | :material-docker: Docker Desktop / Docker Engine | Current |
    | :material-expansion-card: CUDA *(optional)* | For GPU acceleration |

### 1. Bootstrap the project

```bash title="Install the managed Python and sync the locked environment"
uv python install
uv sync --locked
```

```bash title="Full setup (datasets + frontend)"
uv run intellifl-dev setup
```

This keeps local development aligned with the checked-in `uv.lock`, prefers uv-managed CPython, downloads the datasets, and installs frontend npm packages.

!!! tip "Canonical developer entrypoint"
    `uv run intellifl-dev <command>` is the supported cross-platform workflow. `make <target>` is still available as a thin convenience wrapper, but it is no longer the source of truth.

### 2. Start dev servers

```bash
uv run intellifl-dev dev       # Start Docker Compose stack with hot reload
uv run intellifl-dev dev-down  # Stop all services
```

### 3. Run a simulation (CLI)

```bash title="Run the default example simulation"
uv run intellifl-dev sim
# or:
uv run python -m intellifl.simulation_runner config/simulation_strategies/example_strategy_config.json
```

The default config at `config/simulation_strategies/example_strategy_config.json` runs a 10-round FEMNIST simulation with a PID-based defence strategy and a comprehensive `attack_schedule` that demonstrates all 11 attack types (one per round).

**CLI arguments:**

| Argument | Default | Description |
|---|---|---|
| `config_filename` | `example_strategy_config.json` | Path to a strategy config JSON |
| `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `--origin` | `cli` | `cli` or `api` (set automatically by the API) |

---

## :material-folder-open-outline: Examining output

Both options write results to the same directory structure:

```title="Output directory layout"
out/
└── <timestamp>/
    ├── config.json          # copy of the strategy config used
    ├── status.json          # live status (queued / running / completed / failed / stopped)
    ├── output.log           # full simulation log
    ├── csv/
    │   ├── strategy_0.csv   # per-round metrics for strategy 0
    │   └── strategy_1.csv   # per-round metrics for strategy 1 (if multi-strategy)
    ├── plots/               # saved matplotlib figures (PDF)
    │   ├── strategy_0_loss.pdf
    │   └── inter_strategy_comparison.pdf
    └── attack_snapshots/    # HTML reports + pickle dumps (if save_attack_snapshots: true)
        ├── summary.json
        ├── index.html
        └── round_*/
```

---

## :material-test-tube: Running tests and quality checks

```bash title="Quality and test commands"
uv run intellifl-dev check-env        # Verify uv, Python, Docker
uv run intellifl-dev lint             # Code quality checks (ruff, ty, eslint)
uv run intellifl-dev audit            # Security audit with pip-audit
uv run intellifl-dev frontend-audit   # Fix frontend security vulnerabilities
uv run intellifl-dev validate         # Quick feedback: lint + unit tests only
uv run intellifl-dev test             # Full test suite: unit + integration + performance
uv run intellifl-dev baselines        # Record fast simulation baselines for CI
```

!!! tip "Security scanning"
    `uv run intellifl-dev audit` runs `pip-audit` to scan for known vulnerabilities in Python dependencies. `uv run intellifl-dev frontend-audit` handles npm audit fixes.

```bash title="Maintenance commands"
uv run intellifl-dev upgrade       # Update all dependencies to latest versions
uv run intellifl-dev clean         # Remove build artifacts and caches
uv run intellifl-dev reset         # Clean artifacts AND experiment results (out/)
uv run intellifl-dev deps          # Show dependency tree
uv run intellifl-dev docs          # Serve documentation locally (Zensical)
uv run intellifl-dev cache-dir     # Show uv's cache location
uv run intellifl-dev cache-prune   # Remove unused uv cache entries
uv run intellifl-dev yolo          # Nuke and rebuild: clean → setup → upgrade
```

!!! tip "uv cache hygiene"
    Keep uv's default shared cache unless you have a strong reason to move it. `uv run intellifl-dev cache-prune` is safe to run periodically on developer machines. In CI, prefer `uv cache prune --ci`.

---

## :material-wrench-outline: Troubleshooting

### Port already in use

If you see "Address already in use", either:

1. Kill the process using that port:
   ```bash
   # Linux/macOS
   lsof -i :8000
   kill -9 <PID>
   
   # Windows (PowerShell)
   netstat -ano | findstr :8000
   taskkill /PID <PID> /F
   ```

2. Or change the port in `.env`, then re-run:
   ```bash
   uv run intellifl-dev dev
   ```

??? question "Redis connection refused"

    If the API can't reach Redis, ensure Redis is running:

    ```bash
    # Check if Redis container is running
    docker compose ps redis

    # Restart Redis
    docker compose restart redis
    ```

??? question "Simulations queued indefinitely"

    If simulations stay in `queued` state, check the Celery worker:

    ```bash
    docker compose logs celery-worker
    ```

    Ensure `CELERY_CONCURRENCY` is > 0 and the worker is not overloaded.

??? question "Dataset download fails"

    If a dataset fails to download (network timeout or image corruption), clear the cache and retry:

    ```bash
    uv run intellifl-dev clean   # Remove build artifacts and caches
    uv run intellifl-dev sim     # Re-run the simulation
    ```

    HuggingFace datasets are cached in `cache/huggingface/` (configurable via `HF_HOME` env var).

??? question "Frontend linting or npm errors (missing modules)"

    If ESLint fails with "Cannot find module" or npm operations fail mysteriously, `node_modules` may be corrupted (especially on WSL or cross-filesystem setups):

    ```bash
    rm -rf frontend/node_modules
    npm install
    ```

    This clears and reinstalls from `package-lock.json`. A plain `npm install` won't fix corruption because npm caches metadata — a full delete is required.
