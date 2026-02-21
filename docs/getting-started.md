# :material-rocket-launch: Getting Started

## Option A — Docker Compose :material-star:{ title="Recommended" }

The fastest way to run InteFL. Docker Compose brings up the full stack — API, frontend, Redis, Celery worker, documentation site, and optional Celery monitor — with a single command. No Python environment or Node.js install required.

!!! info "Prerequisites"

    - [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Compose)
    - [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) *(optional — for GPU support)*

=== ":material-server-network: Production"

    ```bash title="Start in production mode"
    make prod
    ```

    > Runs `docker compose -f docker-compose.yml up -d`

    | Service | URL | Description |
    |---|---|---|
    | :material-react: Frontend UI | `http://localhost:80` | React dashboard (nginx) |
    | :material-api: Backend API | `http://localhost:8000` | FastAPI + Swagger docs at `/docs` |
    | :material-book-open-variant: Documentation | `http://localhost:8080` | Zensical docs site |

=== ":material-code-braces: Development"

    ```bash title="Start in development mode"
    make dev
    ```

    > Runs `docker compose up`

    Automatically applies `docker-compose.override.yml`, which enables:

    | Service | URL | Description |
    |---|---|---|
    | :material-react: Frontend UI | `http://localhost:5173` | Vite dev server with hot reload |
    | :material-api: Backend API | `http://localhost:8000` | FastAPI with `--reload` |
    | :material-flower-tulip: Celery monitor | `http://localhost:5555` | Flower task queue dashboard |
    | :material-book-open-variant: Documentation | `http://localhost:8080` | Zensical docs site |

**Common commands:**

```bash title="Useful make targets"
make dev                         # Start all services in dev mode (hot reload, Celery monitoring)
make dev-down                    # Stop dev services
make prod                        # Start all services in production mode (detached)
make prod-down                   # Stop prod services
docker compose logs -f           # Tail logs from all services
docker compose logs -f api       # Tail logs from the API service only
```

!!! example "Run a simulation directly via CLI inside the container"

    ```bash
    docker compose run --rm api python -m intellifl.simulation_runner <config.json>
    ```

### :material-key-variant: Environment setup

The project ships a `.env.example` with sensible defaults. Copy it to `.env` before your first run:

```bash title="Create .env file"
cp .env.example .env
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

**Building Docker images:**

```bash
make docker           # Build API image for this machine
make docker-frontend  # Build frontend image for this machine
make docker-all       # Build all images for this machine
make docker-push      # Build all images for amd64+arm64 and push to registry
```

**Persistent volumes:**

| Volume | Description |
|---|---|
| `./out` | Simulation outputs (results, CSVs, plots) — persists across container restarts |
| `./datasets` | Datasets — auto-downloaded on first run, persists across restarts |
| `./config` | Strategy configs (read-only inside container) |
| `redis-data` | Redis task queue state — persists across restarts |

---

## Option B — Local development

Preferred if you are actively modifying the codebase and want to avoid Docker overhead.

!!! info "Prerequisites"

    | Requirement | Version |
    |---|---|
    | :material-language-python: Python | 3.10 – 3.13 |
    | :material-nodejs: Node.js | 20+ |
    | :material-database: Redis | 7+ (local or Docker) |
    | :material-expansion-card: CUDA *(optional)* | For GPU acceleration |

### 1. Install all dependencies

```bash title="Full setup (Python + frontend)"
make setup
```

This runs `setup.sh`, which uses [`uv`](https://github.com/astral-sh/uv) (with a pip fallback) to install the `intellifl` package and all Python dependencies, then installs the frontend npm packages.

??? tip "Install components separately"

    ```bash
    make setup-python     # Python + intellifl package only
    make setup-frontend   # npm install for the React UI only
    ```

### 2. Start dev servers

```bash
make dev
```

Brings up the full Docker Compose stack (API, frontend, Redis, Celery worker, docs, and Celery monitor) with hot reload enabled. Changes to Python or React source files trigger an automatic reload.

To stop all services:

```bash
make dev-down
```

### 3. Run a simulation (CLI)

```bash title="Run the default example simulation"
make sim
# or:
python -m intellifl.simulation_runner config/simulation_strategies/example_strategy_config.json
```

The default config at `config/simulation_strategies/example_strategy_config.json` runs a short FEMNIST simulation with a PID-based defence strategy and an `attack_schedule`.

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

## :material-test-tube: Running tests

```bash title="Test commands"
make test    # lint + unit tests
make lint    # lint only
make sonar   # lint + tests + SonarQube (Docker)
```

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

2. Or change the port via environment variable:
   ```bash
   API_PORT=8001 make dev
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
    make clean   # Remove build artifacts and caches
    make sim     # Re-run the simulation
    ```

    HuggingFace datasets are cached in `cache/huggingface/` (configurable via `HF_HOME` env var).
