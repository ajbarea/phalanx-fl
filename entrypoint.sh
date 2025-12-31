#!/bin/bash
# Downloads datasets on first run if not present, then starts the app
set -e

DATASET_URL="https://fl-dataset-storage.s3.us-east-1.amazonaws.com/datasets.tar"
DATASET_DIR="/app/datasets"

# Check if datasets need to be downloaded
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

# Run the main command (passed as arguments, or default to uvicorn)
exec "$@"
