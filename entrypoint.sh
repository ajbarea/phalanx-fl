#!/bin/bash
# Docker container entrypoint for the FL execution framework.
#
# Downloads datasets on first container run if not present, then executes
# the provided command (defaults to uvicorn). This script is designed to
# run inside the Docker container and handles the one-time dataset setup
# that would otherwise require manual intervention.
#
# Usage: entrypoint.sh [COMMAND] [ARGS...]
#
# Examples:
#   entrypoint.sh                           # Run default uvicorn server
#   entrypoint.sh ./run_experiments.sh      # Run experiments instead
#
# Environment:
#   DATASET_URL: S3 URL for dataset tarball (has default)
#   DATASET_DIR: Directory to store datasets (default: /app/datasets)

set -e

DATASET_URL="https://fl-dataset-storage.s3.us-east-1.amazonaws.com/datasets.tar"
DATASET_DIR="/app/datasets"

# First-run dataset download: bloodmnist presence indicates datasets exist.
# This avoids re-downloading on every container restart while ensuring
# new containers get the required data automatically.
if [ ! -d "$DATASET_DIR/bloodmnist" ]; then
    echo "========================================"
    echo " Downloading datasets (first run only)"
    echo "========================================"

    mkdir -p "$DATASET_DIR"
    cd "$DATASET_DIR"

    echo "Fetching from: $DATASET_URL"
    curl -L --progress-bar -o datasets.tar "$DATASET_URL"

    echo "Extracting..."
    tar -xf datasets.tar
    rm datasets.tar

    echo "Datasets ready!"
    echo ""
    cd /app
fi

# Replace this process with the target command to ensure proper signal handling.
exec "$@"
