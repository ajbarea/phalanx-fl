# IntelliFL - Makefile for common tasks
# Cross-platform compatible (uses shell scripts)

.PHONY: help setup dev sim test lint lint-test sonar clean upgrade docker docker-frontend mutmut mutmut-results mutmut-show

# Default target
help:
	@echo ""
	@echo "IntelliFL - Available Commands"
	@echo "==============================="
	@echo ""
	@echo "Setup:"
	@echo "  make setup            Complete project setup (Python + frontend)"
	@echo "  make setup-python     Python environment only"
	@echo "  make setup-frontend   Frontend dependencies only"
	@echo ""
	@echo "Development:"
	@echo "  make dev              Start dev servers (API + frontend)"
	@echo "  make sim              Run simulation"
	@echo ""
	@echo "Quality:"
	@echo "  make lint             Run linting only"
	@echo "  make test             Run linting + tests"
	@echo "  make mutmut           Run mutation tests (Docker)"
	@echo "  make mutmut-results   View mutation test results"
	@echo "  make mutmut-show ID=1 Show specific mutant details"
	@echo "  make sonar            Run linting + tests + SonarQube (Docker)"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean            Clean build artifacts and caches"
	@echo "  make upgrade          Update dependencies to latest versions"
	@echo ""
	@echo "Docker:"
	@echo "  make docker           Build backend Docker image (intellifl-api)"
	@echo "  make docker-frontend  Build frontend Docker image (intellifl-web)"
	@echo "  make docker-all       Build all Docker images"
	@echo ""

# Setup targets
setup:
	@./setup.sh

setup-python:
	@./reinstall_requirements.sh

setup-frontend:
	@cd frontend && npm install

# Development targets
dev:
	@./run_frontend.sh

sim:
	@./run_simulation.sh

# Quality targets
lint:
	@./tests/lint.sh

test:
	@./tests/lint.sh --test

sonar:
	@./tests/lint.sh --sonar

# Maintenance targets
clean:
	@./clean.sh

upgrade:
	@./update_dependencies.sh

# Docker targets
docker:
	@docker build -t intellifl-api:latest .

docker-frontend:
	@cd frontend && docker build -t intellifl-web:latest .

docker-all: docker docker-frontend
	@echo ""
	@echo "[+] Built IntelliFL components:"
	@echo "  - intellifl-api:latest"
	@echo "  - intellifl-web:latest"
	@echo ""

# Mutation testing (runs in Docker to avoid Windows compatibility issues)
mutmut:
	@docker run --rm --entrypoint sh -v $(CURDIR)/intellifl:/app/intellifl -v $(CURDIR)/tests:/app/tests -v $(CURDIR)/.mutmut-cache:/app/.mutmut-cache intellifl-api:latest -c "cd /app && mutmut run"

mutmut-results:
	@docker run --rm --entrypoint sh -v $(CURDIR)/.mutmut-cache:/app/.mutmut-cache intellifl-api:latest -c "mutmut results"

mutmut-show:
	@docker run --rm --entrypoint sh -v $(CURDIR)/.mutmut-cache:/app/.mutmut-cache intellifl-api:latest -c "mutmut show $(ID)"