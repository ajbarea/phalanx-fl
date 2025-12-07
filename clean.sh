#!/bin/sh
# Cleans the out/ directory, preserving .gitkeep

find out -mindepth 1 ! -name .gitkeep -exec rm -rf {} +
echo "Cleaned out/ directory."

# Clean logs/ directory
if [ -d "logs" ]; then
    find logs -mindepth 1 -exec rm -rf {} +
    echo "Cleaned logs/ directory."
fi

# Clean tests/logs/ directory
if [ -d "tests/logs" ]; then
    find tests/logs -mindepth 1 -exec rm -rf {} +
    echo "Cleaned tests/logs/ directory."
fi

# Clean tool caches
rm -rf .mypy_cache .ruff_cache
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null
echo "Cleaned tool caches (.mypy_cache, .pytest_cache, .ruff_cache)."

# Clean Python bytecode caches
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
echo "Cleaned __pycache__ directories."

# Clean setuptools egg-info
rm -rf *.egg-info
echo "Cleaned egg-info directories."
