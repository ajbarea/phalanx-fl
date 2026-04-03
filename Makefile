##
## IntelliFL — Federated Learning Framework
## Multi-client federated learning with Ray, Flower, and PyTorch
##
## Usage:
##   make help          Show all available commands
##   make setup         Install dependencies + download datasets
##   make dev           Start Docker Compose services
##   make lint          Run code quality checks
##   make test          Run full test suite
##

.PHONY: help setup upgrade yolo dev dev-down sim lint validate test audit clean reset docs deps check-env frontend-audit
.DEFAULT_GOAL := help

# ════════════════════════════════════════════════════════════════════════════
# Environment
# ════════════════════════════════════════════════════════════════════════════

export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
export PYTHONIOENCODING=utf-8

# Use consistent virtual environment across all platforms
export UV_PROJECT_ENVIRONMENT ?= .venv

RULE = @python -c "print('\033[1;96m' + '='*80 + '\033[0m')"
LOG_DIR := tests/logs

# ════════════════════════════════════════════════════════════════════════════
# Pre-flight Checks
# ════════════════════════════════════════════════════════════════════════════

check-env:                 ## Verify uv, Python, and Docker are available
	uv run --no-active python scripts/check_env.py

# ════════════════════════════════════════════════════════════════════════════
# Setup & Maintenance
# ════════════════════════════════════════════════════════════════════════════

setup:                     ## Install all Python dependencies + download datasets
	@if [ -f scripts/setup.py ]; then \
		echo "Running setup..."; \
		uv run --no-active python scripts/setup.py || echo "Setup failed"; \
	else \
		echo "scripts/setup.py not found. Aborting setup."; \
		exit 1; \
	fi

upgrade:                   ## Update all dependencies to latest versions
	uv lock --upgrade
	uv sync

yolo:                      ## Nuke and rebuild: clean → setup → upgrade
	@$(MAKE) --no-print-directory clean
	@$(MAKE) --no-print-directory setup
	@$(MAKE) --no-print-directory upgrade

# ════════════════════════════════════════════════════════════════════════════
# Development Workflows
# ════════════════════════════════════════════════════════════════════════════

dev:                       ## Start all services (Docker Compose)
	docker compose up

dev-down:                  ## Stop all services
	docker compose down

sim:                       ## Run local simulation with optimized Ray environment
	@mkdir -p $(LOG_DIR)
	@env RAY_ENABLE_METRICS_COLLECTION=0 \
	     RAY_METRICS_EXPORT_PORT_ENABLED=0 \
	     RAY_enable_export_api_write=0 \
	     RAY_BACKEND_LOG_LEVEL=fatal \
	     uv run --no-active python -m intellifl.simulation_runner

# ════════════════════════════════════════════════════════════════════════════
# Quality Gates
# ════════════════════════════════════════════════════════════════════════════

lint:                      ## Run code quality checks (ruff format, ruff check, ty)
	uv run --no-active python scripts/lint.py

validate:                  ## Quick validation: lint + unit tests only (fast feedback)
	@$(MAKE) --no-print-directory lint
	uv run --no-active pytest tests/unit/ -n auto -v --tb=short -q

frontend-audit:            ## Fix frontend security vulnerabilities
	@if [ -d "frontend" ]; then cd frontend && npm audit fix; fi

audit:                     ## Audit dependencies for security vulnerabilities
	uv run --no-active python scripts/audit.py

test:                      ## Run full test suite (unit + integration + performance)
	uv run --no-active python scripts/test.py

# ════════════════════════════════════════════════════════════════════════════
# Maintenance
# ════════════════════════════════════════════════════════════════════════════

clean:                     ## Remove build artifacts and caches
	uv run --no-active python scripts/clean_build.py

reset:                     ## Clean artifacts AND experiment results
	uv run --no-active python scripts/clean_build.py --out

docs:                      ## Serve documentation (Zensical)
	uv run --no-active zensical serve

deps:                      ## Show dependency tree
	uv tree

# ════════════════════════════════════════════════════════════════════════════
# Help
# ════════════════════════════════════════════════════════════════════════════

help:                      ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
