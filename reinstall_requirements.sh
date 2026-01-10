#!/bin/sh
# Deletes and recreates the virtual environment

. "$(dirname "$0")/tests/scripts/common.sh"

VENV_NAME=$(get_venv_name)

log_info "Removing existing '$VENV_NAME' directory..."
rm -rf "$VENV_NAME"

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
