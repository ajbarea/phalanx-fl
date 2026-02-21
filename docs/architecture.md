# :material-sitemap: Architecture

## Component overview

```mermaid
flowchart TD
    UI["React / Vite UI<br/>port 5173 (dev) / 80 (prod via nginx)"]
    Docs["Zensical<br/>Documentation · port 8080"]
    API["FastAPI Backend<br/>intellifl.api · port 8000"]
    Redis[(Redis<br/>redis-data volume)]
    Celery["Celery Worker<br/>intellifl.celery_app"]
    SR["SimulationRunner<br/>simulation_runner.py"]
    FedSim["FederatedSimulation<br/>federated_simulation.py"]
    Strat["Aggregation Strategy<br/>FedAvg · Krum · PID · Trust…"]
    Data["Dataset Loader<br/>+ Network Model"]
    Flower["Flower / Ray Engine"]
    Clients["FlowerClient × N<br/>train + evaluate"]

    UI -->|HTTP / SSE| API
    Docs -->|HTTP| Markdown
    API -->|task.delay| Redis
    Redis --> Celery
    Celery --> SR
    SR -->|one or more strategies| FedSim
    FedSim --> Strat
    FedSim --> Data
    Strat --> Flower
    Data --> Flower
    Flower --> Clients
```

---

## :material-puzzle-outline: Key modules

### `simulation_runner.py`

The top-level entry point. Accepts a JSON config file and:

1. Loads the strategy config via `ConfigLoader`
2. Creates a `DirectoryHandler` to manage output directories
3. Acquires a `SimulationLock` (prevents concurrent hardware contention)
4. Iterates through every strategy in the config, creating a `FederatedSimulation` for each
5. Saves CSVs and plots after each strategy completes

It also handles graceful shutdown on `SIGINT`/`SIGTERM` and Ray cleanup between strategies.

### `federated_simulation.py`

Orchestrates a single strategy run:

- Selects the correct **dataset loader** and **network model** based on `dataset_keyword`
- Selects the correct **aggregation strategy** based on `aggregation_strategy_keyword`
- Wraps the strategy and clients in Flower's `ServerApp` / `ClientApp` and calls `run_simulation()`
- After the run, optionally generates attack snapshot HTML reports

### `flower_client.py`

Standard Flower `NumPyClient` subclass. Each virtual client:

- Receives global model parameters from the server
- Runs local training for `num_of_client_epochs` epochs
- Optionally applies attacks from the `attack_schedule` before returning updates
- Reports loss and accuracy back to the server

### `simulation_strategies/`

Each file implements one aggregation strategy as a Flower `Strategy` subclass. Common fields are shared via `common_kwargs` in `FederatedSimulation._assign_aggregation_strategy()`.

### `api/`

FastAPI application with routers for:

| Router | Purpose |
|---|---|
| :material-play-circle: `simulations` | List, inspect, launch, stop, rename, delete simulations; stream status and logs via SSE |
| :material-tray-full: `queue` | Get aggregate queue status counts |
| :material-chart-line: `visualizations` | Fetch plot data JSON and attack snapshot metadata |
| :material-database-check: `datasets` | Validate HuggingFace datasets |
| :material-heart-pulse: `system` | Health check, device and GPU info |
| :material-console: `terminal` | Interactive PTY terminal over WebSocket |
| :material-robot: `assistant` | AI agent chat endpoint |

### `status_tracker.py`

Writes a `status.json` file into the simulation output directory. Transitions: `queued → running → completed / failed / stopped`. The UI polls this file (and the SSE stream) to display live progress.

---

## :material-swap-vertical: Data flow for a simulation

```mermaid
flowchart TD
    S1["1. Config JSON parsed by ConfigLoader"]
    S2["2. StrategyConfig validated by Pydantic"]
    S3["3. DatasetHandler partitions dataset → N client shards"]
    S4["4. FederatedSimulation initialises loaders,<br/>model, strategy, and Flower apps"]
    S5["5. run_simulation() launches Ray actors"]
    Round["For each round<br/>a&#41; Server sends global params<br/>b&#41; Clients train locally<br/>c&#41; Clients apply attack (opt.)<br/>d&#41; Strategy aggregates updates<br/>e&#41; Metrics recorded to history"]
    S6["6. SimulationStrategyHistory → CSV"]
    S7["7. Plots generated and saved"]
    S8["8. Attack snapshots generated (if enabled)"]

    S1 --> S2 --> S3 --> S4 --> S5 --> Round --> S6 --> S7 --> S8
```

---

## :material-folder-outline: Output directory layout

```title="Simulation output structure"
out/
└── <timestamp>/
    ├── config.json
    ├── status.json
    ├── output.log
    ├── csv/
    │   ├── strategy_0.csv
    │   └── strategy_1.csv
    ├── plots/
    │   ├── strategy_0_loss.pdf
    │   └── inter_strategy_comparison.pdf
    └── attack_snapshots/
        ├── summary.json
        ├── index.html
        └── round_N/
            ├── client_M_before.pkl
            ├── client_M_after.pkl
            └── visual_report.html
```

---

## :material-docker: Container and volume lifecycle

=== ":material-code-braces: Development"

    **Applied files:**

    - `docker-compose.yml` (base)
    - `docker-compose.override.yml` (dev overrides)

    **Services:**

    - `api`: FastAPI with `--reload`, hot-sync on `./intellifl` changes
    - `frontend`: Vite dev server (port 5173), hot-sync on `./frontend/src` changes
    - `celery-worker`: Celery worker with hot-sync on `./intellifl` changes
    - `celery-monitor`: Flower monitoring dashboard (port 5555)
    - `docs`: Zensical documentation (port 8080)
    - `redis`: Redis broker with persistent volume

    **Volumes:**

    - `./out`: Mounted RW for simulation outputs
    - `./datasets`: Mounted RW for downloaded datasets
    - `./config`: Mounted RO for strategy configs
    - `redis-data`: Named volume for Redis persistence

=== ":material-server-network: Production"

    **Applied files:**

    - `docker-compose.yml` (base only, no override)

    **Services:**

    - `api`: FastAPI without `--reload`
    - `frontend`: nginx serving prebuilt React bundle (port 80)
    - `celery-worker`: Celery worker
    - `docs`: Zensical documentation (port 8080)
    - `redis`: Redis broker with persistent volume

    **Volumes:**

    - `./out`: Mounted RW for simulation outputs
    - `./datasets`: Mounted RW for downloaded datasets
    - `./config`: Mounted RO for strategy configs
    - `redis-data`: Named volume for Redis persistence (survives container restarts)

    **Network:** `default` — User-defined bridge network (auto-removed on `docker compose down`)

---

## :material-tray-full: Task queuing with Celery + Redis

```mermaid
flowchart TD
    UI["React UI"]
    API["FastAPI"]
    Redis["Redis Broker<br/>Task queue + Result backend"]
    Worker["Celery Worker"]
    SR["SimulationRunner"]
    FS["FederatedSimulation"]

    UI -->|POST /api/simulations| API
    API -->|task.delay| Redis
    Redis -->|pull task| Worker
    Worker -->|exec| SR
    SR --> FS
    FS -->|write status| File["status.json<br/>output.log"]
```

When you submit a simulation via the REST API:

1. The API creates a Celery task and pushes it to Redis
2. The Celery worker picks up the task and invokes `simulation_runner.py`
3. The runner writes `status.json` and `output.log` to the output directory
4. The UI polls these files (and SSE stream) to display live progress
5. Results (CSVs, plots) are written to `./out/<timestamp>/`

!!! info "Fallback mode"

    If Redis is unavailable, the API dispatches simulations as subprocess tasks instead of Celery tasks. The UI still works; queuing is just unavailable.

