#!/bin/bash
# Complete project setup for IntelliFL.
#
# Installs both Python and frontend dependencies in a single command.
# This is the recommended first step after cloning the repository.
#
# Usage: ./setup.sh
#
# What it does:
#   1. Creates Python virtual environment and installs dependencies
#   2. Installs frontend npm packages (React, Vite, ESLint, etc.)
#
# Dependencies: python3 (3.10-3.13), npm
#
# Example:
#   ./setup.sh

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/tests/scripts/common.sh"

navigate_to_root

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                                                            ║"
echo "║              IntelliFL - Complete Setup                    ║"
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

log_info "🚀 Starting complete project setup..."
echo ""

log_info "Step 1/2: Setting up Python environment..."
if [ -f "reinstall_requirements.sh" ]; then
    ./reinstall_requirements.sh
else
    log_error "reinstall_requirements.sh not found!"
    exit 1
fi

echo ""

log_info "Step 2/2: Installing frontend dependencies..."
if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
    cd frontend
    if npm install; then
        log_info "✅ Frontend dependencies installed successfully"
        log_info "   Includes: React, Vite, ESLint, Prettier, sonar-scanner"
    else
        log_error "Failed to install frontend dependencies"
        cd ..
        exit 1
    fi
    cd ..
else
    log_error "Frontend directory or package.json not found!"
    exit 1
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                                                            ║"
echo "║                  ✅ Setup Complete!                        ║"
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

log_info "📋 Next steps:"
echo ""
echo "  Development (with UI):"
echo "    ./run_frontend.sh"
echo ""
echo "  Run simulations (no UI):"
echo "    ./run_simulation.sh"
echo ""
echo "  Code quality checks:"
echo "    ./tests/lint.sh"
echo "    ./tests/lint.sh --test"
echo "    ./tests/lint.sh --sonar  (requires Docker)"
echo ""
echo "  Clean artifacts:"
echo "    ./clean.sh"
echo ""

log_info "📚 Documentation:"
echo "  - SCRIPTS_REFERENCE.md - All scripts explained"
echo "  - docs/DEVELOPMENT_SETUP.md - Development guide"
echo "  - README.md - Project overview"
echo ""
