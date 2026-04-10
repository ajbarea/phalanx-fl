#!/usr/bin/env python3
"""Dataset setup and download orchestration.

Downloads and extracts federated learning datasets from S3 storage if not
already present locally. Shows a progress bar during download and handles
cleanup on failure.
"""

import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

from logging_utils import setup_logger

logger = setup_logger(__name__, "setup_datasets.log")

DATASET_URL = "https://fl-dataset-storage.s3.us-east-1.amazonaws.com/datasets.tar"


def _has_wget() -> bool:
    """Check if wget is available in PATH."""
    return shutil.which("wget") is not None


def _download_with_wget(url: str, dest: Path) -> None:
    """Download using wget for resume support and built-in progress."""
    logger.info("Downloading with wget (resume-capable)...")
    subprocess.run(
        ["wget", "--continue", "--show-progress", "-O", str(dest), url],
        check=True,
    )


def _download_with_urllib(url: str, dest: Path) -> None:
    """Download using urllib with a rich progress bar."""
    try:
        from rich.progress import (
            BarColumn,
            DownloadColumn,
            Progress,
            TransferSpeedColumn,
        )

        # Get file size from headers
        with urllib.request.urlopen(url) as response:
            total = int(response.headers.get("Content-Length", 0))

            with Progress(
                "[progress.description]{task.description}",
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
            ) as progress:
                task = progress.add_task("Downloading", total=total or None)
                with open(dest, "wb") as f:
                    while chunk := response.read(1024 * 256):
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))
    except ImportError:
        logger.info("rich not available, downloading without progress bar...")
        urllib.request.urlretrieve(url, dest)


def setup_datasets() -> None:
    """Download and extract datasets if not already present.

    Prefers wget when available for resume capability and built-in progress.
    Falls back to urllib with a rich progress bar.

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
    datasets_dir.mkdir(exist_ok=True)
    tar_path = datasets_dir / "datasets.tar"

    try:
        logger.info(f"Downloading from {DATASET_URL}...")

        if _has_wget():
            _download_with_wget(DATASET_URL, tar_path)
        else:
            _download_with_urllib(DATASET_URL, tar_path)

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
