#!/usr/bin/env python3
"""Dataset setup and download orchestration.

Downloads and extracts federated learning datasets from S3 storage if not
already present locally. Supports resumable downloads and graceful error
handling with cleanup on failure.
"""

import sys
import tarfile
import urllib.request
from pathlib import Path

from logging_utils import setup_logger

logger = setup_logger(__name__, "logs/setup.log")


def setup_datasets() -> None:
    """Download and extract datasets if not already present.

    Checks for sentinel file (bloodmnist) to determine if datasets exist.
    Downloads from S3 and extracts to datasets/ directory. Cleans up
    temporary tar file on completion or failure.

    Raises:
        SystemExit: On download or extraction failure.
    """
    root = Path(".")
    datasets_dir = root / "datasets"
    sentinel = datasets_dir / "bloodmnist"

    if sentinel.exists():
        logger.info("Datasets already present. Skipping download.")
        return

    logger.info("Datasets not found. Starting download...")
    dataset_url = "https://fl-dataset-storage.s3.us-east-1.amazonaws.com/datasets.tar"
    datasets_dir.mkdir(exist_ok=True)
    tar_path = datasets_dir / "datasets.tar"

    try:
        logger.info(f"Downloading from {dataset_url}...")
        urllib.request.urlretrieve(dataset_url, tar_path)
        logger.info(f"Downloaded to {tar_path}")

        logger.info("Extracting datasets...")
        with tarfile.open(tar_path) as tar:
            tar.extractall(path=datasets_dir)
        logger.info(f"Extracted to {datasets_dir}")

        tar_path.unlink()
        logger.info("Dataset setup complete")
    except Exception as e:
        logger.error(f"Error setting up datasets: {e}", exc_info=True)
        if tar_path.exists():
            tar_path.unlink()
            logger.info("Cleaned up partial download")
        sys.exit(1)


if __name__ == "__main__":
    setup_datasets()
