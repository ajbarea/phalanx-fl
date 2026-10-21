# phalanx-fl

Phalanx is a federated-learning testbed on the current Flower (`flwr`) app-model: a federated LoRA fine-tune of a tiny BERT, with every round and client emitted as OpenTelemetry traces and metrics. Humans start with [README.md](README.md).

## Commands

`make help` lists every target. Run these before a PR:

```bash
make sync   # uv sync --all-extras
make lint   # ruff format --check, ruff check, ty, actionlint
make test   # the suite; downloads a small BERT from the Hugging Face Hub
make audit  # pip-audit over the locked dependencies
```

`make run`, `make smoke` and `make trace` start a local federated simulation and download IMDB, and `make docs` starts a server, and `make otel-up` and `make otel-aspire` start Docker containers: run them only when the task says to. `experiments/*/sweep.py` runs a multi-run grid on a GPU: run it only when asked.

## Rules

- Work in a git worktree and open a pull request; `main` is protected.
- Never commit `COMMITS.md` (a local scratchpad).
- Adapt the app to the latest `flwr` release; do not pin `flwr` back. [ECOSYSTEM.md](ECOSYSTEM.md) gives the reason for each dependency, and `pyproject.toml` holds the versions.
- Any figure about accuracy, loss, round time or payload size traces to a committed run record (`experiments/*/results/`, `results/`) or to a run or test assertion in the same change.
- A SuperLink started by `flwr run` keeps its first worktree's venv and cwd for every later run. Stop `flower-superexec` and `flower-superlink` before running from another worktree, and read a run's result from `Received N results and 0 failures`: `flwr run` exits 0 even when every client fails.
- README's Python and Flower badges and its `[tool.flwr.app.config]` table restate `pyproject.toml`: update them together.
- `uv.lock` is generated: change it with `uv lock`, never by hand. CI runs `uv lock --check`.

## State

`IMPL.md` holds the current slice and next step; `ROADMAP.md` the long view.
`.claude/skill-context.md` holds the facts the techne skills read for this repo.
