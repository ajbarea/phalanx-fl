## Phalanx — federated learning on the latest Flower (flwr 1.31 app-model).
## An OTel-observable FL research testbed: a federated LoRA fine-tune of a tiny BERT,
## aggregating only the adapters.
##
## Common targets:
##   make sync     Install dependencies (CPU torch + HF extras + dev group)
##   make lint     ruff format --check + ruff check + ty
##   make test     Run the test suite
##   make smoke    Fast 2-round federated simulation (sanity check)
##   make run      Full federated simulation (flwr run, streamed)
##   make trace    Run with console OTel traces (no collector needed)
##   make audit    Security scan (pip-audit)
##
## Simulation knobs: app config via --run-config 'num-server-rounds=5 partitioner=iid';
## federation size via --federation-config 'options.num-supernodes=10' (flwr 1.31 keeps
## simulation settings in ~/.flwr/config.toml, auto-created on first run with 5 nodes).

.PHONY: help sync lint fmt test test-cov run smoke trace audit docs clean
.DEFAULT_GOAL := help

export UV_PROJECT_ENVIRONMENT ?= .venv
# Run inside the project env with the model/data stack present (CPU torch + HF).
UVX := uv run --no-active --extra hf --extra torch

help:                      ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n",$$1,$$2}'

sync:                      ## Install all dependencies (CPU torch + HF extras + dev group)
	uv sync --extra hf --extra torch

lint:                      ## ruff format check + ruff lint + ty type-check
	uv run --no-active ruff format --check .
	uv run --no-active ruff check .
	uv run --no-active ty check

fmt:                       ## Apply ruff formatting + autofixes
	uv run --no-active ruff format .
	uv run --no-active ruff check --fix .

test:                      ## Run the test suite
	$(UVX) python -m pytest

test-cov:                  ## Run the test suite with coverage
	$(UVX) python -m pytest --cov=phalanx --cov-report=term-missing

run:                       ## Full federated simulation (flwr run, streamed)
	$(UVX) flwr run . local-simulation --stream

smoke:                     ## Fast 2-round federated simulation (sanity check)
	$(UVX) flwr run . local-simulation --stream --run-config "num-server-rounds=2"

trace:                     ## Run with console OTel traces (no collector needed)
	OTEL_TRACES_EXPORTER=console $(UVX) flwr run . local-simulation --stream

audit:                     ## Security scan (pip-audit over the locked deps)
	uv run --no-active pip-audit

docs:                      ## Serve the Zensical docs site locally
	uv run --no-active zensical serve

clean:                     ## Remove caches + build artifacts
	rm -rf .ruff_cache .pytest_cache .hypothesis dist build site
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
