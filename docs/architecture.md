# :material-sitemap: Architecture

## Component overview

<div class="pfig" markdown="0">
  <div class="pfig-row"><div class="pnode"><b>React / Vite UI</b><span>:5173 dev · :80 prod (nginx)</span></div></div>
  <div class="pfig-flow">HTTP / SSE</div>
  <div class="pfig-row"><div class="pnode"><b>FastAPI Backend</b><span>intellifl.api · :8000</span></div></div>
  <div class="pfig-flow">task.delay</div>
  <div class="pfig-row"><div class="pnode pnode--purple"><b>Redis</b><span>broker · redis-data volume</span></div></div>
  <div class="pfig-flow"></div>
  <div class="pfig-row"><div class="pnode"><b>Celery Worker</b><span>intellifl.celery_app</span></div></div>
  <div class="pfig-flow"></div>
  <div class="pfig-row"><div class="pnode"><b>SimulationRunner</b><span>simulation_runner.py</span></div></div>
  <div class="pfig-flow">one or more strategies</div>
  <div class="pfig-row"><div class="pnode"><b>FederatedSimulation</b><span>federated_simulation.py</span></div></div>
  <div class="pfig-flow"></div>
  <div class="pfig-row pfig-branch">
    <div class="pnode pnode--purple"><b>Aggregation Strategy</b><span>FedAvg · Krum · PID · Trust…</span></div>
    <div class="pnode"><b>Dataset Loader</b><span>+ Network Model</span></div>
  </div>
  <div class="pfig-flow"></div>
  <div class="pfig-row"><div class="pnode"><b>Flower / Ray Engine</b></div></div>
  <div class="pfig-flow"></div>
  <div class="pfig-row"><div class="pnode"><b>FlowerClient × N</b><span>train + evaluate</span></div></div>
</div>

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
- Wraps the strategy and clients in Flower's `ServerApp` / `ClientApp` and launches Flower's simulation engine
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
| :material-play-circle: `simulations` | List, inspect, launch, stop, rename, delete simulations; stream status and logs via Server-Sent Events (SSE) |
| :material-tray-full: `queue` | Get aggregate queue status counts |
| :material-chart-line: `visualizations` | Fetch plot data JSON and attack snapshot metadata |
| :material-database-check: `datasets` | Validate HuggingFace datasets |
| :material-heart-pulse: `system` | Health check, device and GPU info |
| :material-console: `terminal` | Interactive PTY terminal over WebSocket |
| :material-robot: `assistant` | AI agent chat endpoint |

!!! info "Real-time Streaming"
    The simulations endpoint streams live updates via SSE using named events (`status` and `output`). The UI subscribes to these events to display real-time progress without polling. Output logs are streamed line-by-line as they're written to disk.

### `status_tracker.py`

Writes a `status.json` file into the simulation output directory. This is the **sole writer** of status updates: all transitions (`queued → running → completed / failed / stopped`) go through `StatusTracker`, ensuring consistency and preventing race conditions. The UI polls this file and listens to SSE `status` events to display live progress.

---

## :material-swap-vertical: Data flow for a simulation

<div class="pfig" markdown="0">
  <div class="pfig-row"><div class="pnode"><b>1 · Config JSON</b><span>parsed by ConfigLoader</span></div></div>
  <div class="pfig-flow"></div>
  <div class="pfig-row"><div class="pnode"><b>2 · StrategyConfig</b><span>validated by Pydantic</span></div></div>
  <div class="pfig-flow"></div>
  <div class="pfig-row"><div class="pnode"><b>3 · DatasetHandler</b><span>partitions dataset → N client shards</span></div></div>
  <div class="pfig-flow"></div>
  <div class="pfig-row"><div class="pnode"><b>4 · FederatedSimulation</b><span>initialises loaders, model, strategy, Flower apps</span></div></div>
  <div class="pfig-flow"></div>
  <div class="pfig-row"><div class="pnode"><b>5 · Flower engine</b><span>launches Ray actors</span></div></div>
  <div class="pfig-flow"></div>
  <div class="pfig-loop">
    <div class="pfig-loop-h">for each round</div>
    <ol>
      <li>Server sends global params</li>
      <li>Clients train locally</li>
      <li>Clients apply attack (optional)</li>
      <li>Strategy aggregates updates</li>
      <li>Metrics recorded to history</li>
    </ol>
  </div>
  <div class="pfig-flow"></div>
  <div class="pfig-row"><div class="pnode"><b>6 · History → CSV</b><span>SimulationStrategyHistory</span></div></div>
  <div class="pfig-flow"></div>
  <div class="pfig-row"><div class="pnode"><b>7 · Plots</b><span>generated + saved</span></div></div>
  <div class="pfig-flow"></div>
  <div class="pfig-row"><div class="pnode"><b>8 · Attack snapshots</b><span>if enabled</span></div></div>
</div>

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

    **Start:** `docker compose -f docker-compose.yml up -d`

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

---

## :material-tray-full: Task queuing with Celery + Redis

<div class="pfig" markdown="0">
  <div class="pfig-row"><div class="pnode"><b>React UI</b></div></div>
  <div class="pfig-flow">POST /api/simulations</div>
  <div class="pfig-row"><div class="pnode"><b>FastAPI</b></div></div>
  <div class="pfig-flow">task.delay</div>
  <div class="pfig-row"><div class="pnode pnode--purple"><b>Redis Broker</b><span>task queue + result backend</span></div></div>
  <div class="pfig-flow">pull task</div>
  <div class="pfig-row"><div class="pnode"><b>Celery Worker</b></div></div>
  <div class="pfig-flow">exec</div>
  <div class="pfig-row"><div class="pnode"><b>SimulationRunner</b></div></div>
  <div class="pfig-flow"></div>
  <div class="pfig-row"><div class="pnode"><b>FederatedSimulation</b></div></div>
  <div class="pfig-flow">write status</div>
  <div class="pfig-row"><div class="pnode"><b>status.json · output.log</b></div></div>
</div>

When you submit a simulation via the REST API:

1. The API creates a Celery task and pushes it to Redis
2. The Celery worker picks up the task and invokes `simulation_runner.py`
3. The runner writes `status.json` and `output.log` to the output directory
4. The UI polls these files (and SSE stream) to display live progress
5. Results (CSVs, plots) are written to `./out/<timestamp>/`

!!! info "Fallback mode"

    If Redis is unavailable, the API dispatches simulations as subprocess tasks instead of Celery tasks. The UI still works; queuing is just unavailable.
