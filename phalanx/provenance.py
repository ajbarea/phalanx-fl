"""Run-provenance manifest: the static record that makes a run reproducible + citable.

Pairs with the OTel traces — the traces are the dynamic record of a run, the manifest
is the static provenance (git commit, package versions, run config, final metrics). A
lightweight extraction of the old app's reproducibility manifest, aimed at FAIR / IEEE
artifact-evaluation criteria without dragging in its heavyweight system-introspection.
"""

from __future__ import annotations

import json
import platform
import subprocess
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

# The packages whose versions actually pin a run's behaviour.
_TRACKED_PACKAGES = ("flwr", "flwr-datasets", "torch", "transformers", "peft")


def _git(*args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL, text=True).strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for pkg in _TRACKED_PACKAGES:
        try:
            versions[pkg] = version(pkg)
        except PackageNotFoundError:
            continue
    return versions


def run_manifest(*, run_config: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    """Capture a reproducibility manifest for one federated run."""
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "git": {
            "commit": _git("rev-parse", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        },
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": _package_versions(),
        "run_config": dict(run_config),
        "metrics": dict(metrics),
    }


def write_manifest(manifest: dict[str, Any], directory: str | Path = "runs") -> Path:
    """Write the manifest as timestamped JSON under ``directory``; return its path."""
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = str(manifest.get("generated_at") or "run").replace(":", "-")
    path = out_dir / f"run-{stamp}.json"
    path.write_text(json.dumps(manifest, indent=2, default=str))
    return path
