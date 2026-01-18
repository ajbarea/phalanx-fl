#!/bin/bash
# Clean build artifacts, caches, and temporary files from the project.
#
# Removes logs, tool caches, coverage data, Python bytecode, and other
# generated files while preserving source code, datasets, and configuration.
# Safe to run at any time - will not delete source code or datasets.
#
# Usage: ./clean.sh
#
# What gets cleaned:
#   - logs/ and tests/logs/ directories
#   - Tool caches: .mypy_cache, .pytest_cache, .ruff_cache
#   - Coverage data: .coverage files
#   - Python bytecode: __pycache__ directories
#   - Test artifacts: .hypothesis, MagicMock directories
#   - Build artifacts: *.egg-info, frontend/dist
#   - Playwright MCP artifacts: .playwright-mcp
#   - Dependency backups: uv.lock.backup.*
#
# What is preserved:
#   - Source code (intellifl/, tests/, frontend/src/)
#   - Datasets (datasets/)
#   - Configuration files
#   - Virtual environment (.venv/)
#   - Git history (.git/)

. "$(dirname "$0")/tests/scripts/common.sh"

# ============================================================================
# Cleanup Operations
# ============================================================================

if [ -d "logs" ]; then
    find logs -mindepth 1 -depth -exec rm -rf {} +
    log_info "Cleaned logs/ directory."
fi

if [ -d "tests/logs" ]; then
    find tests/logs -mindepth 1 -depth -exec rm -rf {} +
    log_info "Cleaned tests/logs/ directory."
fi

rm -rf .mypy_cache .ruff_cache
find . -type d -name ".pytest_cache" -depth -exec rm -rf {} + 2>/dev/null
log_info "Cleaned tool caches (.mypy_cache, .pytest_cache, .ruff_cache)."

rm -f .coverage .coverage.*
rm -f tests/.coverage tests/.coverage.*
log_info "Cleaned coverage data files."

find . -type d -name "__pycache__" -depth -exec rm -rf {} + 2>/dev/null
log_info "Cleaned __pycache__ directories."

find . -type d -name ".hypothesis" -depth -exec rm -rf {} + 2>/dev/null
log_info "Cleaned .hypothesis directories."

find . -type d -name "MagicMock" -depth -exec rm -rf {} + 2>/dev/null
log_info "Cleaned MagicMock directories."

rm -rf ./*.egg-info
log_info "Cleaned egg-info directories."

if [ -d ".playwright-mcp" ]; then
    rm -rf .playwright-mcp
    log_info "Cleaned .playwright-mcp directory."
fi

if [ -d "frontend/dist" ]; then
    rm -rf frontend/dist
    log_info "Cleaned frontend/dist/ directory."
fi

rm -f uv.lock.backup.*
log_info "Cleaned uv.lock backup files."
