# :material-console: CLI Reference

The canonical developer workflow uses the cross-platform `intellifl-dev` CLI. Every command is invoked through `uv run`:

```bash
uv run intellifl-dev <command> [-- <args...>]
```

!!! tip "`make` compatibility"

    `make <target>` is still available as a thin wrapper, but `intellifl-dev` is the source of truth for all supported commands.

---

## :material-check-network: Environment

| Command | Description |
|---|---|
| `check-env` | Verify that `uv`, Python, and Docker are available and correctly configured |

```bash
uv run intellifl-dev check-env
```

---

## :material-package-variant-closed: Setup & Maintenance

| Command | Description |
|---|---|
| `setup` | Install all Python dependencies and download datasets |
| `upgrade` | Update all dependencies to their latest versions |
| `yolo` | Nuke and rebuild: runs `clean` → `setup` → `upgrade` in sequence |

```bash title="Bootstrap a fresh clone"
uv run intellifl-dev setup
```

```bash title="Full rebuild from scratch"
uv run intellifl-dev yolo
```

---

## :material-code-braces: Development Workflows

| Command | Description |
|---|---|
| `dev` | Start all services via Docker Compose (hot reload in dev mode) |
| `dev-down` | Stop all services |
| `docs` | Serve the documentation site locally (Zensical) |
| `sim` | Run a local simulation with optimized Ray environment |
| `baselines` | Record fast simulation baselines for CI regression checks |

=== ":material-play-circle: Start development"

    ```bash
    uv run intellifl-dev dev
    ```

    This starts the full Docker Compose stack: API, frontend, Redis, Celery worker, and docs site. In development mode, `docker-compose.override.yml` is automatically applied for hot reload.

=== ":material-stop-circle: Stop development"

    ```bash
    uv run intellifl-dev dev-down
    ```

=== ":material-flask-outline: Run a simulation"

    ```bash
    uv run intellifl-dev sim
    ```

    Runs the default example config at `config/simulation_strategies/example_strategy_config.json`. Pass extra arguments after `--`:

    ```bash
    uv run intellifl-dev sim -- path/to/custom_config.json --log-level DEBUG
    ```

=== ":material-book-open-variant: Serve docs"

    ```bash
    uv run intellifl-dev docs
    ```

    Launches Zensical's local dev server with live reload.

---

## :material-shield-check: Quality Gates

| Command | Description |
|---|---|
| `lint` | Run code quality checks (ruff format, ruff check, ty) |
| `validate` | Quick feedback: lint + unit tests only |
| `test` | Full test suite: unit + integration + performance |
| `audit` | Audit Python dependencies for known security vulnerabilities (pip-audit) |
| `frontend-audit` | Fix frontend (npm) security vulnerabilities |

```bash title="Fast feedback loop"
uv run intellifl-dev validate
```

```bash title="Full CI-equivalent suite"
uv run intellifl-dev test
```

!!! info "Security scanning"

    `audit` runs `pip-audit` against the locked dependency set. `frontend-audit` runs `npm audit fix` in the `frontend/` directory.

---

## :material-wrench-outline: Maintenance

| Command | Description |
|---|---|
| `deps` | Show the dependency tree |
| `clean` | Remove build artifacts and caches |
| `reset` | Clean artifacts **and** experiment results (`out/`) |
| `cache-dir` | Show uv's cache directory location |
| `cache-prune` | Prune unused entries from uv's cache |

```bash title="Clean up disk space"
uv run intellifl-dev clean
```

```bash title="Nuclear option — wipe everything including results"
uv run intellifl-dev reset
```

!!! warning "Destructive commands"

    `reset` deletes the `out/` directory containing all simulation results. Use `clean` if you only want to remove build artifacts.

---

## :material-keyboard: Passthrough arguments

Any command accepts extra arguments after a `--` separator. These are forwarded directly to the underlying script or tool:

```bash
uv run intellifl-dev sim -- config/custom.json --log-level DEBUG
uv run intellifl-dev test -- -k test_flower_client -v
```
