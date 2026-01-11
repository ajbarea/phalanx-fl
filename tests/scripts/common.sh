#!/bin/bash
# Common shell utilities for the FL execution framework.
#
# This library provides reusable functions for logging, system utilities,
# Python environment management, dependency installation, and simulation
# helpers. Source this file to access its functions - do not execute directly.
#
# Function Categories:
#   - Logging: Structured output with log levels and file support
#   - System: Command detection, navigation, and hardware queries
#   - Python Environment: Interpreter discovery and virtual environment setup
#   - Dependencies: Package installation with uv/pip fallback
#   - Python Execution: Unicode-aware script execution
#   - Simulation: Output directory management and reporting
#
# Dependencies: python3 (3.10-3.13), psutil (for CPU detection)

set -eu

# ============================================================================
# Logging
# ============================================================================

# Log an informational message to stdout and optionally to a log file.
#
# Arguments:
#   $1: Message to log
#
# Globals:
#   LOG_FILE: If set, message is appended to this file
log_info() {
    if [ -n "${LOG_FILE:-}" ]; then
        echo "✅ $1" | tee -a "$LOG_FILE"
    else
        echo "✅ $1"
    fi
}

# Log a warning message to stdout and optionally to a log file.
#
# Arguments:
#   $1: Warning message to log
#
# Globals:
#   LOG_FILE: If set, message is appended to this file
log_warning() {
    if [ -n "${LOG_FILE:-}" ]; then
        echo "⚠️  $1" | tee -a "$LOG_FILE"
    else
        echo "⚠️  $1"
    fi
}

# Log an error message to stderr and optionally to a log file.
#
# Arguments:
#   $1: Error message to log
#
# Globals:
#   LOG_FILE: If set, message is appended to this file
log_error() {
    if [ -n "${LOG_FILE:-}" ]; then
        echo "❌ $1" | tee -a "$LOG_FILE" >&2
    else
        echo "❌ $1" >&2
    fi
}

# Set up logging to a timestamped file in the specified directory.
#
# Creates the log directory if it doesn't exist and initializes a new log
# file with a timestamp. Exports LOG_FILE and LOG_DIR for use by other
# functions.
#
# Arguments:
#   $1: Log directory path (default: tests/logs)
#   $2: Log file prefix (default: script)
#
# Globals:
#   LOG_FILE: Set to the path of the created log file
#   LOG_DIR: Set to the log directory path
setup_logging_with_file() {
    _log_dir="${1:-tests/logs}"
    _log_prefix="${2:-script}"

    mkdir -p "$_log_dir"
    LOG_FILE="$_log_dir/${_log_prefix}_$(date +%Y%m%d_%H%M%S).log"
    : > "$LOG_FILE"

    log_info "📝 Logging to: $LOG_FILE"

    export LOG_FILE
    LOG_DIR="$_log_dir"
    export LOG_DIR
}

# Output text to stdout and optionally append to a log file.
#
# Arguments:
#   $*: Text to output
#
# Globals:
#   LOG_FILE: If set, text is appended to this file
log_and_tee() {
    if [ -n "${LOG_FILE:-}" ]; then
        printf "%s\n" "$*" | tee -a "$LOG_FILE"
    else
        printf "%s\n" "$*"
    fi
}

# ============================================================================
# System
# ============================================================================

# Check if a command is available in the system PATH.
#
# Arguments:
#   $1: Command name to check
#
# Returns:
#   0: Command exists
#   1: Command not found
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Navigate to the project root directory.
#
# Detects the project root by looking for pyproject.toml or requirements.txt
# with a src directory. If not already at root, navigates up from common
# script locations (tests/scripts, tests).
navigate_to_root() {
    if { [ -f "pyproject.toml" ] || [ -f "requirements.txt" ]; } && [ -d "src" ]; then
        return
    fi
    script_dir="$(cd "$(dirname "$0")" && pwd)"

    case "$script_dir" in
        *"/tests/scripts")
            cd "$script_dir/../.."
            ;;
        *"/tests")
            cd "$script_dir/.."
            ;;
        *)
            log_warning "Could not determine project root. Staying in $(pwd)."
            ;;
    esac
}

# Get the number of physical CPU cores.
#
# Uses psutil to query physical cores, falling back to logical cores if
# physical count is unavailable, and finally to 1 if all detection fails.
#
# Globals:
#   PYTHON_CMD: Uses this to run Python, finds interpreter if not set
#
# Returns:
#   Prints the number of physical cores to stdout
get_physical_cores() {
    if [ -z "${PYTHON_CMD:-}" ]; then
        find_python_interpreter
    fi
    run_python -c "import psutil; print(psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 1)"
}

# ============================================================================
# Python Environment
# ============================================================================

# Execute Python with the discovered interpreter and optional arguments.
#
# Wrapper function that handles both regular python commands and the Windows
# py launcher with version arguments.
#
# Arguments:
#   $@: Arguments to pass to Python
#
# Globals:
#   PYTHON_CMD: Python command to use, finds interpreter if not set
#   PYTHON_ARGS: Additional arguments for Python (e.g., version for py)
run_python() {
    if [ -z "${PYTHON_CMD:-}" ]; then
        find_python_interpreter
    fi

    if [ -n "${PYTHON_ARGS:-}" ]; then
        "$PYTHON_CMD" "$PYTHON_ARGS" "$@"
    else
        "$PYTHON_CMD" "$@"
    fi
}

# Find and set a compatible Python interpreter (3.10-3.13).
#
# Searches for Python in order of preference: python3.13, python3.12,
# python3.11, python3.10, python3. Falls back to Windows py launcher if
# direct commands aren't found. Validates version compatibility before
# selecting.
#
# Globals:
#   PYTHON_CMD: Set to the discovered Python command
#   PYTHON_ARGS: Set to version args for py launcher, empty otherwise
#
# Returns:
#   0: Compatible Python found
#   1: No compatible Python found (exits script)
find_python_interpreter() {
    if [ -n "${PYTHON_CMD:-}" ] && command_exists "$PYTHON_CMD"; then
        return 0
    fi

    log_info "🔍 Searching for a compatible Python interpreter..."
    for version in python3.13 python3.12 python3.11 python3.10 python3; do
        if command_exists "$version"; then
            if "$version" -c "import sys; sys.exit(not (sys.version_info >= (3, 10) and sys.version_info < (3, 14)))" 2>/dev/null; then
                PYTHON_CMD="$version"
                export PYTHON_CMD
                PYTHON_ARGS=""
                export PYTHON_ARGS
                log_info "Found compatible Python: $PYTHON_CMD"
                return 0
            fi
        fi
    done

    if command_exists py; then
        for py_version in "-3.13" "-3.12" "-3.11" "-3.10" "-3"; do
             if py "$py_version" -c "import sys; sys.exit(not (sys.version_info >= (3, 10) and sys.version_info < (3, 14)))" 2>/dev/null; then
                PYTHON_CMD="py"
                export PYTHON_CMD
                PYTHON_ARGS="$py_version"
                export PYTHON_ARGS
                log_info "Found compatible Python via 'py' launcher: $PYTHON_CMD $PYTHON_ARGS"
                return 0
            fi
        done
    fi

    log_error "Python 3.9, 3.10, or 3.11 was not found. Please install a compatible version."
    exit 1
}

# Set up and activate the virtual environment if available.
#
# Searches for .venv or venv directories, activates the environment, and
# sets PYTHON_CMD to the venv's Python interpreter. Handles both Unix and
# Windows venv structures.
#
# Globals:
#   VIRTUAL_ENV: If already set, uses this as the venv directory
#   VENV_DIR: Set to the discovered venv directory path
#   PYTHON_CMD: Set to the venv's Python interpreter
#   PYTHON_ARGS: Cleared when using venv Python
#
# Returns:
#   0: Virtual environment activated or already active
setup_virtual_environment() {
    if [ -n "${VIRTUAL_ENV:-}" ]; then
        VENV_DIR="$VIRTUAL_ENV"
        export VENV_DIR
        return 0
    fi

    # Wait briefly if venv directory exists but activation scripts don't yet.
    # On Windows, venv creation may not be atomic.
    if [ ! -d ".venv/Scripts" ] && [ ! -d ".venv/bin" ] && [ -d ".venv" ]; then
        sleep 1
    elif [ ! -d "venv/Scripts" ] && [ ! -d "venv/bin" ] && [ -d "venv" ]; then
        sleep 1
    fi

    log_info "🔌 Searching for virtual environment..."
    venv_path=""
    if [ -d ".venv" ]; then
        venv_path=".venv"
    elif [ -d "venv" ]; then
        venv_path="venv"
    fi

    if [ -n "$venv_path" ]; then
        log_info "Found virtual environment in '$venv_path', activating..."
        VENV_DIR="$(cd "$venv_path" && pwd)"
        export VENV_DIR
        if [ -f "$VENV_DIR/Scripts/activate" ]; then
            # shellcheck source=/dev/null
            . "$VENV_DIR/Scripts/activate"
            if [ -f "$VENV_DIR/Scripts/python.exe" ]; then
                PYTHON_CMD="$VENV_DIR/Scripts/python.exe"
                export PYTHON_CMD
                PYTHON_ARGS=""
                export PYTHON_ARGS
            fi
        else
            # shellcheck source=/dev/null
            . "$VENV_DIR/bin/activate"
            if [ -f "$VENV_DIR/bin/python" ]; then
                PYTHON_CMD="$VENV_DIR/bin/python"
                export PYTHON_CMD
                PYTHON_ARGS=""
                export PYTHON_ARGS
            fi
        fi
        log_info "Virtual environment activated."
    else
        log_warning "No virtual environment found (expected '.venv' or 'venv')."
    fi
}

# Get the name of the virtual environment directory.
#
# Returns:
#   Prints ".venv" if it exists, otherwise "venv"
get_venv_name() {
    if [ -d ".venv" ]; then
        echo ".venv"
    else
        echo "venv"
    fi
}

# Ensure a virtual environment exists and activate it.
#
# Checks for an existing venv and activates it. If no venv is found,
# warns the user to run reinstall_requirements.sh.
#
# Returns:
#   0: Virtual environment found and activated
#   1: No virtual environment found
ensure_virtual_environment() {
    if [ -z "${VIRTUAL_ENV:-}" ] && ! [ -d ".venv" ] && ! [ -d "venv" ]; then
        log_warning "Virtual environment not found. You may need to run './reinstall_requirements.sh' to create one."
        return 1
    fi
    setup_virtual_environment
}

# Configure environment for Unicode support in Python.
#
# Globals:
#   PYTHONIOENCODING: Set to utf-8
setup_unicode_env() {
    export PYTHONIOENCODING="utf-8"
    log_info "Unicode environment configured (PYTHONIOENCODING=utf-8)"
}

# Configure environment variables for joblib and parallel processing.
#
# Sets CPU count to physical cores only to avoid joblib oversubscription
# with logical cores. Also configures OpenMP and Ray environment variables.
#
# Globals:
#   LOKY_MAX_CPU_COUNT: Set to physical core count
#   KMP_DUPLICATE_LIB_OK: Set to TRUE for OpenMP compatibility
#   PYTHONWARNINGS: Configured to ignore threadpoolctl warnings
#   RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO: Set to 0 for Ray compatibility
setup_joblib_env() {
    LOKY_MAX_CPU_COUNT=$(get_physical_cores)
    export LOKY_MAX_CPU_COUNT
    export KMP_DUPLICATE_LIB_OK=TRUE
    export PYTHONWARNINGS="ignore::RuntimeWarning:threadpoolctl"
    export RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO=0
}

# ============================================================================
# Dependencies
# ============================================================================

# Install Python dependencies using uv or pip.
#
# Prefers uv sync for faster installation, falls back to pip if uv is
# unavailable or fails.
#
# Arguments:
#   $1: Requirements file path (default: requirements.txt)
#
# Returns:
#   0: Dependencies installed successfully
#   1: Installation failed
install_requirements() {
    requirements_file="${1:-requirements.txt}"
    
    if command_exists uv; then
        log_info "📦 Using uv to sync dependencies..."
        if uv sync; then
            log_info "Dependencies synced successfully with uv."
            return 0
        fi
        log_warning "uv sync failed, falling back to pip..."
    fi

    if [ -f "$requirements_file" ]; then
        log_info "📦 Installing requirements from $requirements_file..."
        if pip install -r "$requirements_file"; then
            log_info "Requirements installed successfully."
        else
            log_error "Failed to install requirements from $requirements_file"
            return 1
        fi
    else
        log_warning "Neither uv nor requirements file $requirements_file found, skipping installation."
    fi
}

# Check for a tool and install it if missing.
#
# Arguments:
#   $1: Tool name to check
#   $2: Installation command to run if tool is missing
#   $3: Check command (default: command_exists)
#
# Returns:
#   0: Tool exists or was installed successfully
#   1: Installation failed
check_and_install_tool() {
    tool_name="$1"
    install_command="$2"
    check_command="${3:-command_exists}"

    if ! $check_command "$tool_name"; then
        log_warning "$tool_name not found. Attempting to install..."
        if eval "$install_command"; then
            log_info "$tool_name installed successfully."
        else
            log_error "Failed to install $tool_name. Please install manually."
            return 1
        fi
    fi
}

# Install frontend dependencies using npm.
#
# Checks for npm availability and frontend directory, then installs
# dependencies from package.json.
#
# Returns:
#   0: Frontend dependencies installed successfully
#   1: npm not found, frontend directory missing, or installation failed
install_frontend_dependencies() {
    if ! command_exists npm; then
        log_error "npm not found. Please install Node.js and npm first."
        return 1
    fi

    if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
        log_info "📦 Installing frontend dependencies..."
        if (cd frontend && npm install); then
            log_info "Frontend dependencies installed successfully"
            return 0
        else
            log_error "Failed to install frontend dependencies"
            return 1
        fi
    else
        log_warning "Frontend directory or package.json not found, skipping frontend installation."
        return 1
    fi
}

# ============================================================================
# Python Execution
# ============================================================================

# Execute a Python script with Unicode support and virtual environment.
#
# Configures Unicode encoding, activates virtual environment if available,
# and runs the specified Python script.
#
# Arguments:
#   $1: Path to Python script
#   $@: Additional arguments to pass to the script
#
# Globals:
#   PYTHONIOENCODING: Set to utf-8
#   PYTHON_CMD: Uses discovered Python interpreter
run_python_with_unicode() {
    script_path="$1"
    shift

    setup_unicode_env

    if [ -n "${VIRTUAL_ENV:-}" ] || [ -d "venv" ] || [ -d ".venv" ]; then
        setup_virtual_environment
    fi

    if [ -z "${PYTHON_CMD:-}" ]; then
        find_python_interpreter
    fi

    PYTHONIOENCODING=utf-8 run_python "$script_path" "$@"
}


# ============================================================================
# Simulation
# ============================================================================

# Display information about simulation output location.
#
# Shows the output directory and finds the most recent timestamped
# subdirectory if available.
#
# Arguments:
#   $1: Output directory path (default: out/)
show_simulation_output_info() {
    output_dir="${1:-out/}"
    _pwd="$(pwd)"

    rel_output_dir="${output_dir#"$_pwd"/}"

    latest_dir=""
    if [ -d "$output_dir" ]; then
        latest_dir=$(find "$output_dir" -maxdepth 1 -type d -name "*-*-*_*-*-*" | sort | tail -1)
        if [ -n "$latest_dir" ]; then
            latest_dir="${latest_dir#"$_pwd"/}"
        fi
    fi

    log_info "🎉 Simulation completed successfully!"

    if [ -n "$latest_dir" ]; then
        log_info "📁 Results saved to: $latest_dir"
        log_info "📊 Contains: plots, CSV data, configs, datasets, logs"
    else
        log_info "📁 Results saved to: $rel_output_dir"
    fi
}

# ============================================================================
# Globals
# ============================================================================

# Global variable to store the discovered Python command.
# Set by find_python_interpreter() and used by run_python().
PYTHON_CMD=""
export PYTHON_CMD
