#!/bin/bash
# Delete and recreate the Python virtual environment with fresh dependencies.
#
# Removes the existing virtual environment directory and creates a new one,
# installing all dependencies. Prefers uv for faster environment creation,
# falling back to pip if uv is unavailable.
#
# Usage: ./reinstall_requirements.sh
#
# Dependencies: python3 (3.10-3.13), uv (optional, preferred)

. "$(dirname "$0")/tests/scripts/common.sh"

VENV_NAME=$(get_venv_name)
force_remove_venv "$VENV_NAME"

# Prefer uv for faster environment creation and dependency resolution.
# Fall back to pip if uv is unavailable (common on minimal systems).
if command_exists uv; then
    log_info "Creating and syncing environment with uv..."
    uv sync
else
    find_python_interpreter
    log_info "Creating new '$VENV_NAME' virtual environment via venv..."
    run_python -m venv "$VENV_NAME"
    setup_virtual_environment
    log_info "Upgrading pip..."
    run_python -m pip install --upgrade pip
    install_requirements
fi
