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

.PHONY: help setup upgrade yolo dev dev-down sim lint validate test audit clean reset docs check-env baselines
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

validate:                  ## Quick validation: lint + unit tests only (fast feedback)
	@$(UV_DEV) validate

audit:                     ## Auto-fix and audit security vulnerabilities (backend + frontend)
	@$(UV_DEV) audit

test:                      ## Run full test suite (unit + integration + performance)
	@$(UV_DEV) test

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
# Help
# ════════════════════════════════════════════════════════════════════════════

help:                      ## Show this help message
	@$(UV_DEV) help
