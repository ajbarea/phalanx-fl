# skill-context — phalanx-fl

Repo-specific facts for canonical skills under `~/.claude/skills/`. Injected
into each skill at invocation via `!cat .claude/skill-context.md`. Update on
toolchain / path / tooling changes.

## repo

- name: phalanx-fl
- package_root: `phalanx/`
- language: Python (flwr 1.31 app-model)
- cli_entrypoint: none — a plain `Makefile` dispatches tools directly (no dev-runner CLI)
- app components: `phalanx.server_app:app` (ServerApp), `phalanx.client_app:app` (ClientApp)
- has: flwr Message API, HuggingFace + PEFT/LoRA, OpenTelemetry, flwr-datasets

## audit

The Makefile calls tools directly (ruff/ty/pytest/flwr), so there is **no
dev-runner log archive** (`logs/dev-*.log`) — read terminal output directly.

Targets, in dependency order:

1. `make sync` — `uv sync --extra hf --extra torch` (CPU torch + HF stack + dev group).
2. `make lint` — `ruff format --check` + `ruff check` + `ty check`.
3. `make test` — `uv run --extra hf --extra torch python -m pytest`.
4. `make audit` — `pip-audit` over the locked deps.

"Am I ready to push" probe = `make lint` then `make test`.

Do-not-run targets (long-running / external state): `make run`, `make smoke`,
`make trace` (each spins a local SuperLink + Ray simulation and downloads IMDB),
`make docs` (zensical serve).

Tests download `google/bert_uncased_L-2_H-128_A-2` (~18 MB) from the HF Hub; set
`HF_HUB_DISABLE_TELEMETRY=1`. The full federated run additionally downloads IMDB.

## ci_audit

Referenced configs a CI failure can trace to:
- `pyproject.toml`
- `Makefile`
- `.github/workflows/ci.yml` (lint / test / audit jobs)
- `phalanx/*.py`

Tool error markers (extend the default grep set):
- `ruff` (lint), `ty` (type-check), `pytest` (test failures / collection errors),
  `pip-audit` (advisory findings).

Expected external PR checks: Codecov (see `codecov.yml`), GitGuardian.

## fragile_docs

README claims that trace to code (no automated gate yet — verify by hand on edit):
- Python badge `3.12+` ← `requires-python` in `pyproject.toml`.
- Flower badge `v1.31+` ← `flwr` floor in `pyproject.toml`.
- The `[tool.flwr.app.config]` table in the README ← the keys in `pyproject.toml`.

## scan_scope

Skip paths (vendored / generated / out-of-scope):
- `.venv/`, `dist/`, `build/`, `site/`
- `__pycache__/`, `.ruff_cache/`, `.pytest_cache/`, `.hypothesis/`
- `uv.lock`, `~/.flwr/` (per-user flwr state, not in-repo)

Subagent scan-area split:
- Core package: `phalanx/**/*.py`
- Tests: `tests/**/*.py`
- Config/build: `pyproject.toml`, `Makefile`, `.github/workflows/**`, `zensical.toml`
- Docs (opt-in): `docs/**/*.md`

## docs_site

- config: `zensical.toml`
- workflow: `.github/workflows/docs.yml`
- css_files: `docs/stylesheets/extra.css`
- js_files: `docs/javascripts/*.js`
- build_command: `uv run zensical build --clean`
- site_url: `https://ajbarea.github.io/phalanx-fl/`
- action_pins (expected): pinned to commit SHAs; audit against the workflow for drift.

## theoros

Interactive surface = the Flower simulation. Drive it observably with:
`OTEL_TRACES_EXPORTER=console uv run flwr run . local-simulation --stream`
(prints round + client OTel spans to the terminal as the run progresses).
Spectator attaches read-only to the same tmux session. The run downloads IMDB on
first use and trains on CPU, so a 2-round `--run-config "num-server-rounds=2"` is
the quick play-through.
