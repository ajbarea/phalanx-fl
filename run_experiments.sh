#!/bin/bash
# Run experiment configurations with automatic PYTHONPATH setup.
#
# This wrapper script handles PYTHONPATH configuration and Python interpreter
# discovery before launching the interactive experiment runner. It supports
# both Unix and Windows virtual environments.
#
# Usage: ./run_experiments.sh [OPTIONS]
#
# Options are passed through to experiment_runner.py. Run with --help for
# available options.
#
# Examples:
#   ./run_experiments.sh              # Interactive mode
#   ./run_experiments.sh --help       # Show experiment runner options
#
# Dependencies: python3 (3.10-3.13)

# PYTHONPATH must include project root for Python to find intellifl/ modules.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export PYTHONPATH="$SCRIPT_DIR"

# Prefer virtual environment Python for consistent dependencies.
if [ -f "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
    PYTHON="$SCRIPT_DIR/.venv/Scripts/python.exe"
elif [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
else
    PYTHON="python"
fi

"$PYTHON" "$SCRIPT_DIR/tests/scripts/experiment_runner.py" "$@"
