#!/bin/bash

# Docker-based dev server for Intel Macs
# Runs PyTorch 2.6.0 in a Linux container, bypassing Intel Mac limitations
#
# Usage:
#   ./run_docker.sh              Start fullstack (recommended)
#   docker compose up --build    Manual start
#   docker compose down          Stop services
#
# Endpoints:
#   Frontend: http://localhost:5173
#   API:      http://localhost:8000
#
# Requirements:
#   Docker - https://docs.docker.com/get-docker/
set -e

echo "🐳 Starting FL Framework with Docker..."
echo ""
echo "Services:"
echo "  - API:      http://localhost:8000"
echo "  - Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Build and start
docker compose up --build



