#!/bin/bash
# Wrapper script for experiment_runner.py that handles PYTHONPATH automatically

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Set PYTHONPATH to project root
export PYTHONPATH="$SCRIPT_DIR"

# Use virtual environment Python if available, otherwise system Python
if [ -f "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
    PYTHON="$SCRIPT_DIR/.venv/Scripts/python.exe"
elif [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
else
    PYTHON="python"
fi

# Run the experiment runner with all arguments passed through
"$PYTHON" "$SCRIPT_DIR/tests/scripts/experiment_runner.py" "$@"
