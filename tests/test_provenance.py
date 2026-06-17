"""Run-provenance manifest capture + write."""

from __future__ import annotations

import json
from pathlib import Path

from phalanx.provenance import run_manifest, write_manifest


def test_run_manifest_captures_provenance() -> None:
    m = run_manifest(run_config={"num-server-rounds": 3}, metrics={"accuracy": 0.61})
    assert m["run_config"]["num-server-rounds"] == 3
    assert m["metrics"]["accuracy"] == 0.61
    # The package versions that pin a run's behaviour.
    assert "flwr" in m["packages"]
    assert m["python"] and m["platform"]
    assert m["generated_at"]


def test_write_manifest_roundtrips(tmp_path: Path) -> None:
    m = run_manifest(run_config={}, metrics={})
    path = write_manifest(m, directory=tmp_path)
    assert path.exists() and path.suffix == ".json"
    loaded = json.loads(path.read_text())
    assert loaded["packages"] == m["packages"]
