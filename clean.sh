#!/bin/sh
# Cleans the out/ directory, preserving .gitkeep

. "$(dirname "$0")/tests/scripts/common.sh"

find out -mindepth 1 -depth ! -name .gitkeep -exec rm -rf {} +
log_info "Cleaned out/ directory."

# Clean logs/ directory
if [ -d "logs" ]; then
    find logs -mindepth 1 -depth -exec rm -rf {} +
    log_info "Cleaned logs/ directory."
fi

# Clean tests/logs/ directory
if [ -d "tests/logs" ]; then
    find tests/logs -mindepth 1 -depth -exec rm -rf {} +
    log_info "Cleaned tests/logs/ directory."
fi

# Clean tool caches
rm -rf .mypy_cache .ruff_cache
find . -type d -name ".pytest_cache" -depth -exec rm -rf {} + 2>/dev/null
log_info "Cleaned tool caches (.mypy_cache, .pytest_cache, .ruff_cache)."

# Clean Python bytecode caches
find . -type d -name "__pycache__" -depth -exec rm -rf {} + 2>/dev/null
log_info "Cleaned __pycache__ directories."

# Clean Hypothesis testing cache
find . -type d -name ".hypothesis" -depth -exec rm -rf {} + 2>/dev/null
log_info "Cleaned .hypothesis directories."

# Clean MagicMock artifacts
find . -type d -name "MagicMock" -depth -exec rm -rf {} + 2>/dev/null
log_info "Cleaned MagicMock directories."

# Clean setuptools egg-info
rm -rf *.egg-info
log_info "Cleaned egg-info directories."

# Clean Playwright MCP artifacts
if [ -d ".playwright-mcp" ]; then
    rm -rf .playwright-mcp
    log_info "Cleaned .playwright-mcp directory."
fi
