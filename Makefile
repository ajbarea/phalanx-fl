##
## IntelliFL — Federated Learning Framework
## Multi-client federated learning with Ray, Flower, and PyTorch
##
## Usage:
##   uv run intellifl-dev help   Show all available commands
##   uv run intellifl-dev setup  Install dependencies + download datasets
##   uv run intellifl-dev dev    Start Docker Compose services
##   uv run intellifl-dev lint   Run code quality checks
##   uv run intellifl-dev test   Run full test suite
##   uv run intellifl-dev baselines  Record fast simulation baselines for CI
##   make <target>               Optional compatibility wrapper
##

.PHONY: help setup upgrade yolo dev dev-down sim lint validate test test-unit test-integration test-performance audit clean reset docs check-env baselines logs logs-tail
.DEFAULT_GOAL := help

export UV_PROJECT_ENVIRONMENT ?= .venv
UV_DEV := uv run --no-active intellifl-dev

# ════════════════════════════════════════════════════════════════════════════
# Pre-flight Checks
# ════════════════════════════════════════════════════════════════════════════

check-env:                 ## Verify uv, Python, and Docker are available
	@$(UV_DEV) check-env

# ════════════════════════════════════════════════════════════════════════════
# Setup & Maintenance
# ════════════════════════════════════════════════════════════════════════════

setup:                     ## Install all Python dependencies + download datasets
	@$(UV_DEV) setup

upgrade:                   ## Update all dependencies to latest versions
	@$(UV_DEV) upgrade

yolo:                      ## Nuke and rebuild: clean → setup → upgrade
	@$(UV_DEV) yolo

# ════════════════════════════════════════════════════════════════════════════
# Development Workflows
# ════════════════════════════════════════════════════════════════════════════

dev:                       ## Start all services (Docker Compose)
	@$(UV_DEV) dev

dev-down:                  ## Stop all services
	@$(UV_DEV) dev-down

sim:                       ## Run local simulation with optimized Ray environment
	@$(UV_DEV) sim

# ════════════════════════════════════════════════════════════════════════════
# Quality Gates
# ════════════════════════════════════════════════════════════════════════════

lint:                      ## Run code quality checks (ruff format, ruff check, ty)
	@$(UV_DEV) lint

validate:                  ## Quick validation: lint + unit tests only
	@$(UV_DEV) validate

test:                      ## Run full test suite (unit + integration + performance)
	@$(UV_DEV) test

test-unit:                 ## Run unit tests only (parallel with CPU detection)
	@$(UV_DEV) test -- --unit

test-integration:          ## Run integration tests only
	@$(UV_DEV) test -- --integration

test-performance:          ## Run performance tests only
	@$(UV_DEV) test -- --performance

audit:                     ## Auto-fix and audit security vulnerabilities (backend + frontend)
	@$(UV_DEV) audit

baselines:                 ## Record fast simulation baselines for CI
	@$(UV_DEV) baselines -- --all-fast

# ════════════════════════════════════════════════════════════════════════════
# Maintenance
# ════════════════════════════════════════════════════════════════════════════

clean:                     ## Remove build artifacts and caches
	@$(UV_DEV) clean

reset:                     ## Clean artifacts AND experiment results
	@$(UV_DEV) reset

docs:                      ## Serve documentation (Zensical)
	@$(UV_DEV) docs

# ════════════════════════════════════════════════════════════════════════════
# Logs
#   These bypass intellifl-dev — opening the CLI truncates logs/dev-latest.log,
#   which would erase what we're trying to read.
# ════════════════════════════════════════════════════════════════════════════

logs:                      ## Show the last 200 lines of logs/dev-latest.log
	@tail -n 200 logs/dev-latest.log 2>/dev/null || echo "no logs yet — run any make target first"

logs-tail:                 ## Follow logs/dev-latest.log (Ctrl-C to exit)
	@tail -f logs/dev-latest.log

# ════════════════════════════════════════════════════════════════════════════
# Help
# ════════════════════════════════════════════════════════════════════════════

help:                      ## Show this help message
	@$(UV_DEV) help
