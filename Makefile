# IntelliFL - Makefile for common tasks
# Cross-platform compatible (uses shell scripts)

ARCH            := $(shell uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')
NATIVE_PLATFORM := linux/$(ARCH)

.PHONY: help setup setup-python setup-frontend dev dev-down prod prod-down sim lint test sonar clean upgrade docker docker-frontend docker-all docker-push mutmut mutmut-results mutmut-show

# Default target
help:
	@echo ""
	@echo "IntelliFL - Available Commands"
	@echo "==============================="
	@echo ""
	@echo "Quick start: make setup && make dev"
	@echo ""
	@echo "Setup:"
	@echo "  make setup            Complete project setup (Python + frontend)"
	@echo "  make setup-python     Python environment only"
	@echo "  make setup-frontend   Frontend dependencies only"
	@echo ""
	@echo "Development:"
	@echo "  make dev              Start all services in dev mode (hot reload, Celery monitoring)"
	@echo "  make dev-down         Stop all services"
	@echo ""
	@echo "Production:"
	@echo "  make prod             Start all services in production mode"
	@echo "  make prod-down        Stop prod services"
	@echo ""
	@echo "Simulation:"
	@echo "  make sim              Run a simulation"
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
	@echo "  make docker           Build API image for this machine (load to local Docker)"
	@echo "  make docker-frontend  Build frontend image for this machine (load to local Docker)"
	@echo "  make docker-all       Build all images for this machine (load to local Docker)"
	@echo "  make docker-push      Build all images for amd64+arm64 and push to registry"
	@echo ""

# Setup targets
setup:
	@bash setup.sh

setup-python:
	@bash reinstall_requirements.sh

setup-frontend:
	@cd frontend && npm install

# Development targets
dev:
	@docker compose up

dev-down:
	@docker compose down

prod:
	@docker compose -f docker-compose.yml up -d

prod-down:
	@docker compose -f docker-compose.yml down

sim:
	@bash run_simulation.sh

# Quality targets
lint:
	@bash tests/lint.sh

test:
	@bash tests/lint.sh --test

sonar:
	@bash tests/lint.sh --sonar

# Maintenance targets
clean:
	@bash clean.sh

upgrade:
	@bash update_dependencies.sh

# Docker targets
docker:
	@docker buildx bake -f docker-bake.hcl api --load --set "api.platforms=$(NATIVE_PLATFORM)"

docker-frontend:
	@docker buildx bake -f docker-bake.hcl frontend --load --set "frontend.platforms=$(NATIVE_PLATFORM)"

docker-all:
	@docker buildx bake -f docker-bake.hcl --load --set "*.platforms=$(NATIVE_PLATFORM)"
	@echo ""
	@echo "[+] Built IntelliFL components for $(NATIVE_PLATFORM):"
	@echo "  - intellifl-api:latest"
	@echo "  - intellifl-web:latest"
	@echo ""

docker-push:
	@docker buildx bake -f docker-bake.hcl --push
	@echo ""
	@echo "[+] Pushed IntelliFL components (linux/amd64 + linux/arm64):"
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
