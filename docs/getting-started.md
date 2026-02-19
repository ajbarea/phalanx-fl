# Getting Started

## Option A — Docker Compose (recommended)

The fastest way to run InteFL. Docker Compose brings up the full stack — API, frontend, Redis, Celery worker, and Celery monitor — with a single command. No Python environment or Node.js install required.

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Compose). Add the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) if you want GPU support.

```bash
docker compose up --build
```

| Service | URL | Description |
|---|---|---|
| Frontend UI | `http://localhost:5173` | React dashboard |
| Backend API | `http://localhost:8000` | FastAPI + Swagger docs at `/docs` |
| Celery monitor | `http://localhost:5555` | Flower task queue dashboard |

**Common commands:**

```bash
docker compose up --build        # Build images and start all services
docker compose up -d             # Start in background (detached)
docker compose down              # Stop all services
docker compose logs -f           # Tail logs from all services
```

**Run a simulation directly via CLI inside the container:**

```bash
docker compose run --rm api python -m intellifl.simulation_runner <config.json>
```

**Environment variables** (override in a `.env` file or shell):

| Variable | Default | Description |
|---|---|---|
| `API_PORT` | `8000` | Host port for the API |
| `FRONTEND_PORT` | `5173` | Host port for the frontend |
| `CELERY_CONCURRENCY` | `1` | Number of parallel Celery workers |

**Persistent volumes:**

| Volume | Description |
|---|---|
| `./out` | Simulation outputs (results, CSVs, plots) |
| `./datasets` | Datasets — auto-downloaded on first run |
| `./config` | Strategy configs (read-only inside container) |

---

## Option B — Local development

Preferred if you are actively modifying the codebase.

**Prerequisites:**

| Requirement | Version |
|---|---|
| Python | 3.10 – 3.12 |
| Node.js | 18+ |
| Redis | Any recent version |
| CUDA (optional) | For GPU acceleration |

### 1. Install all dependencies

```bash
make setup
```

This runs `setup.sh`, which uses [`uv`](https://github.com/astral-sh/uv) to install the `intellifl` package and all Python dependencies, then installs the frontend npm packages.

Individual steps if needed:

```bash
make setup-python     # Python + intellifl package only
make setup-frontend   # npm install for the React UI only
```

### 2. Start dev servers

```bash
make dev
```

Starts the FastAPI backend (port `8000`) and the Vite dev server (port `5173`) with live log tailing. Changes to Python or React source files trigger an automatic reload.

With heartbeat monitoring:

```bash
make dev-monitored
```

### 3. Run a simulation (CLI)

```bash
make sim
# or:
python -m intellifl.simulation_runner example_strategy_config.json
```

The default config at `config/simulation_strategies/example_strategy_config.json` runs a short FEMNIST simulation with a PID-based defence strategy and an `attack_schedule`.

**CLI arguments:**

| Argument | Default | Description |
|---|---|---|
| `config_file` | `example_strategy_config.json` | Path to a strategy config JSON |
| `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `--origin` | `cli` | `cli` or `api` (set automatically by the API) |

---

## Examining output

Both options write results to the same directory structure:

```
out/
└── 20240215_123456/
    ├── config.json          # copy of the strategy config used
    ├── status.json          # live status (queued / running / completed / failed)
    ├── output.log           # full simulation log
    ├── csv/
    │   └── strategy_0.csv   # per-round metrics
    ├── plots/               # saved matplotlib figures (PDF)
    └── attack_snapshots/    # HTML reports + pickle dumps (if enabled)
```

---

## Running tests

```bash
make test    # lint + unit tests
make lint    # lint only
```
