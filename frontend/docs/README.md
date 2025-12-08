# Frontend

A React 19 UI for the `fl-execution-framework`, powered by Vite, React Bootstrap, and Recharts.

## Features

- **Dashboard**: Real-time simulation status, metrics, and comparisons.
- **Simulation Config**: Form-based validation for datasets, strategies, and attacks.
- **Experiment Queue**: Batch scheduling with strategy variations.
- **Visualizations**: Interactive plots (Recharts) with zoom/brush controls.
- **Terminal**: Integrated xterm.js terminal with WebSocket backend connection.
- **Attacks**: Dynamic poisoning configuration (data & weights) with visual snapshots.

## Quick Start

Run the all-in-one startup script (requires Python + Node.js):

```bash
./run_frontend.sh
```

This starts:

- **API**: `http://localhost:8000`
- **UI**: `http://localhost:5173`

## Project Structure

```text
frontend/src/
├── components/
│   ├── common/           # Reusable UI (Button, Icon, Modal)
│   ├── features/         # Domain components
│   │   ├── education/    # Config explainers
│   │   ├── experiment-queue/
│   │   ├── simulation-details/
│   │   ├── simulation-form/
│   │   └── simulation-list/
│   └── layout/           # App shell (Navbar, PageContainer)
├── pages/
│   ├── Dashboard/        # Main simulation list
│   ├── ExperimentQueue/  # Batch job manager
│   ├── NewSimulation/    # Config form
│   ├── QueueStatus/      # Job progress
│   ├── SimulationDetails/# Results view
│   └── Terminal/         # Full-screen terminal
└── hooks/                # Data fetching & state logic
```

## Documentation

- [**Dataset Guide**](./datasets.md): Loading HuggingFace/local datasets.
- [**Attack Guide**](./attacks.md): Configuring poisoning attacks.

## API Overview

The frontend consumes a **FastAPI** backend:

- `GET /api/simulations`: List runs.
- `POST /api/simulations`: Launch run.
- `WS /api/terminal`: Interactive terminal session.
- `GET /api/datasets/validate`: Check HuggingFace dataset compatibility.
