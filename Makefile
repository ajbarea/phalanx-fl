# IntelliFL - Makefile for common tasks
# Cross-platform compatible (uses shell scripts)

.PHONY: help setup dev sim test lint lint-test sonar clean docker docker-frontend

# Default target
help:
	@echo ""
	@echo "IntelliFL - Available Commands"
	@echo "==============================="
	@echo ""
	@echo "Setup:"
	@echo "  make setup          Complete project setup (Python + frontend)"
	@echo "  make setup-python   Python environment only"
	@echo "  make setup-frontend Frontend dependencies only"
	@echo ""
	@echo "Development:"
	@echo "  make dev            Start dev servers (API + frontend)"
	@echo "  make sim            Run simulation"
	@echo ""
	@echo "Quality:"
	@echo "  make lint           Run linting only"
	@echo "  make test           Run linting + tests"
	@echo "  make sonar          Run linting + tests + SonarQube (requires Docker)"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean          Clean build artifacts and caches"
	@echo ""
	@echo "Docker:"
	@echo "  make docker         Build backend Docker image"
	@echo "  make docker-frontend Build frontend Docker image"
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

# Docker targets
docker:
	@docker build -t intellifl-backend .

docker-frontend:
	@cd frontend && docker build -t intellifl-frontend .
