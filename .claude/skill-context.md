# skill-context — phalanx-fl

Repo-specific facts for canonical skills under `~/.claude/skills/`. Injected
into each skill at invocation via `!cat .claude/skill-context.md`. Update on
toolchain / path / tooling changes.

## repo

- name: phalanx-fl
- package_root: `intellifl/`
- language: Python (plus React frontend under `frontend/`)
- cli_entrypoint: `intellifl-dev` (module: `intellifl.dev_cli`)
- runner_module: `intellifl/dev_runner.py::SessionLog.session_footer`
- has: docker, frontend, datasets, attack vocabularies

## audit

Full audit = 10 `make` targets, in order:

1. `make clean` — wipes `__pycache__`, `.ruff_cache`, `.pytest_cache`, `out/`, stale logs.
2. `make check-env` — uv / Python / Docker on PATH.
3. `make setup` — `uv sync` + dataset download.
4. `make lint` — ruff format, ruff check, ty.
5. `make test-unit` — pytest on `tests/unit/`, parallelized.
6. `make test-integration` — pytest on `tests/integration/`, serial.
7. `make test-performance` — pytest on `tests/performance/`, serial.
8. `make test` — combined suite.
9. `make validate` — fast `lint + unit`. The "am I ready to push" probe.
10. `make audit` — `pip-audit` + frontend advisories. Supply-chain gate.

Fast audit = `clean → check-env → setup → validate`. Four commands.

Stop-early phase: Phase 1 (clean / check-env / setup). If any fails, abort.

Log archive: `logs/dev-<YYYYMMDDTHHMMSS>-<cmd>.log` + pointer `logs/dev-latest.log`.
`SUMMARY` block is emitted by `intellifl/dev_runner.py::SessionLog.session_footer`.
Do **not** read `dev-latest.log` (overwritten each invocation).

Do-not-run targets (long-running / expensive / external-state):
`make docs` (zensical serve), `make dev`, `make sim`, `make baselines`.

## ci_audit

Referenced configs a CI failure can trace to:
- `pyproject.toml`
- `Makefile`
- `intellifl/dev_cli.py`
- `scripts/*.py`

Tool error markers that may appear in CI logs (extend the default grep set):
- `pip-audit` (advisory findings)
- `ty` (type-check errors)
- `ruff` (lint errors)
- `pytest` (test failures / collection errors)

Expected external PR checks: codecov (see `codecov.yml`), GitGuardian.

## slop_ground_truth

Sources of truth for numeric performance / scale claims:

- Performance tests: `tests/performance/test_memory_usage.py`, `tests/performance/test_scalability.py`
- Recorded baselines: output of `make baselines`

Any quantitative perf/scale claim not traceable to one of those is slop.

## fragile_docs

README / docs numbers that trace to code, gated by `scripts/check_readme_claims.py` (runs in the CI Security Audit job):

- Strategy count — `len(set(STRATEGY_REGISTRY.values()))` (`intellifl/simulation_strategies/__init__.py`); asserted in README ("N Aggregation Strategies") and `docs/index.md` (hero tagline + feature card).
- Attack count — `len(DATA_ATTACK_TYPE_NAMES) + len(WEIGHT_ATTACK_TYPE_NAMES)` (`attack_utils/poisoning.py` + `weight_poisoning.py`); asserted in README ("N Attack Types") and `docs/index.md`.
- Python + Flower version badges — `requires-python` and the `flwr` floor in `pyproject.toml`; asserted in the README shields badges.

Add a claim → append a check to `build_checks()` in that script. Roster name *lists* aren't auto-checked; the count gate flags when one needs an update.

## scan_scope

Skip paths (vendored, generated, or out-of-scope):
- `.venv/`, `node_modules/`, `dist/`, `build/`, `site/`, `out/`
- `__pycache__/`, `.ruff_cache/`, `.pytest_cache/`, `.hypothesis/`
- `uv.lock`, `datasets/`, `cache/`
- `frontend/node_modules/`, `intellifl/attack_utils/vocabularies/`
- `docs/assets/`, `logs/`, `intellifl.egg-info/`

Subagent scan-area split:
- Core package: `intellifl/**/*.py`
- Scripts: `scripts/**/*.py`
- Tests: `tests/**/*.py`
- Frontend: `frontend/**/*.{ts,tsx,js,jsx,vue,svelte}` (skip `frontend/node_modules/`)
- Config/build: `pyproject.toml`, `Makefile`, `.github/workflows/**`, `zensical.toml`, `docker-compose*.yml`, `Dockerfile`, `.vscode/**`
- Docs (opt-in): `docs/**/*.md`

## docs_site

- config: `zensical.toml`
- workflow: `.github/workflows/docs.yml`
- css_files: single `docs/stylesheets/extra.css`
- js_files: `docs/javascripts/*.js`
- build_command: `uv run zensical build --clean`
- site_url: `https://<owner>.github.io/phalanx-fl/`
- action_pins (expected): pinned to tagged versions; audit against the workflow for drift.
