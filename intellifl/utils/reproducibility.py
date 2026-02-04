"""Utilities for gathering reproducibility metadata for federated learning experiments."""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import psutil
import torch


def get_system_metadata() -> dict[str, Any]:
    """Gather hardware and software system metadata.

    Returns:
        Dictionary containing system specifications and package versions.
    """
    metadata: dict[str, Any] = {
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "python": {
            "version": sys.version,
            "implementation": platform.python_implementation(),
        },
        "hardware": {
            "cpu_count": psutil.cpu_count(logical=True),
            "physical_cores": psutil.cpu_count(logical=False),
            "ram_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        },
    }

    # Gather GPU info if available
    if torch.cuda.is_available():
        gpus = []
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            gpus.append(
                {
                    "index": i,
                    "name": props.name,
                    "total_memory_gb": round(props.total_memory / (1024**3), 2),
                    "capability": f"{props.major}.{props.minor}",
                }
            )
        metadata["hardware"]["gpus"] = gpus

    # Gather Git info if available
    try:
        git_branch = (
            subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            .decode("ascii")
            .strip()
        )
        git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("ascii").strip()
        metadata["git"] = {
            "branch": git_branch,
            "commit": git_commit,
        }
    except (subprocess.SubprocessError, FileNotFoundError):
        logging.debug("Git metadata not available")

    # Gather Pip freeze
    try:
        pip_freeze = subprocess.check_output([sys.executable, "-m", "pip", "freeze"]).decode(
            "utf-8"
        )
        metadata["packages"] = pip_freeze.splitlines()
    except subprocess.SubprocessError:
        logging.debug("Pip freeze metadata not available")

    return metadata


def get_file_checksum(filepath: str | Path) -> str:
    """Calculate SHA-256 checksum of a file.

    Args:
        filepath: Path to the file.

    Returns:
        Hexadecimal SHA-256 checksum.
    """
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read in blocks of 4KB
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def save_reproducibility_manifest(
    output_dir: str | Path, config_path: str | Path | None = None
) -> None:
    """Save a reproducibility manifest (MANIFEST.json) to the output directory.

    Args:
        output_dir: Directory where the manifest will be saved.
        config_path: Path to the primary config.json file to checksum.
    """
    output_path = Path(output_dir)
    manifest_path = output_path / "MANIFEST.json"

    import datetime

    manifest = {
        "manifest_version": "1.0",
        "timestamp": datetime.datetime.now().isoformat(),
        "system": get_system_metadata(),
    }

    if config_path:
        config_path = Path(config_path)
        if config_path.exists():
            manifest["config_checksum"] = {
                "file": config_path.name,
                "sha256": get_file_checksum(config_path),
            }

    try:
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=4)
        logging.debug(f"Reproducibility manifest saved to {manifest_path}")
    except OSError as e:
        logging.error(f"Failed to save reproducibility manifest: {e}")
