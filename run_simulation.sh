#!/bin/bash
# Run the federated learning simulation with automatic environment setup.
#
# Sets up the Python virtual environment if needed, downloads required datasets
# if not present, and executes the simulation runner. Results are saved to the
# out/ directory with timestamped subdirectories.
#
# Usage: ./run_simulation.sh
#
# The script will:
#   1. Create/activate virtual environment (runs reinstall_requirements.sh if missing)
#   2. Download datasets from S3 if datasets/bloodmnist/ doesn't exist
#   3. Run the simulation via intellifl.simulation_runner
#
# Dependencies: python3 (3.10-3.13), wget (optional, falls back to Python urllib)

. "$(dirname "$0")/tests/scripts/common.sh"

if ! ensure_virtual_environment; then
    log_warning "Running reinstall_requirements.sh to create '.venv'..."
    ./reinstall_requirements.sh
    setup_virtual_environment
fi

find_python_interpreter
setup_joblib_env

export RAY_ENABLE_METRICS_COLLECTION=0
export RAY_METRICS_EXPORT_PORT_ENABLED=0
export RAY_enable_export_api_write=0
# Ray log levels: debug=0, info=1, warning=2, error=3, fatal=4
export RAY_BACKEND_LOG_LEVEL=fatal
# Skip raylet log level initialization messages
export RAY_DEDUP_LOGS_SKIP_REGEX="logging\.cc.*Set ray log level"

# Check for datasets by looking for bloodmnist as a sentinel directory.
# All datasets are distributed together, so if one exists, all should exist.
if [ ! -d "datasets/bloodmnist" ]; then
    log_info "Datasets not found. Starting download..."
    DATASET_URL="https://fl-dataset-storage.s3.us-east-1.amazonaws.com/datasets.tar"

    mkdir -p datasets
    _orig_dir="$(pwd)"
    cd datasets || exit 1

    # Prefer wget for better progress reporting and resume capability.
    # Fall back to Python's urllib if wget is unavailable (minimal dependencies).
    if command_exists wget; then
        log_info "Downloading with wget..."
        wget "$DATASET_URL"
    else
        log_info "Downloading with Python..."
        run_python -c "import urllib.request; print('Downloading datasets.tar...'); urllib.request.urlretrieve('$DATASET_URL', 'datasets.tar')"
    fi

    log_info "Extracting datasets..."
    tar -xf datasets.tar
    rm datasets.tar
    cd "$_orig_dir" || exit 1
fi

log_info "🚀 Initializing simulation..."
if run_python -m intellifl.simulation_runner; then
    echo ""
    show_simulation_output_info "out/"
else
    log_error "❌ Simulation failed. Check the logs above for details."
    exit 1
fi
