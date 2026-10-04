"""Run-provenance manifest capture + write."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def test_run_manifest_keeps_global_metrics_apart_from_client_metrics() -> None:
    m = run_manifest(
        run_config={},
        metrics={"1": {"accuracy": 0.9}},
        global_metrics={"0": {"accuracy": 0.5}, "1": {"accuracy": 0.7}},
    )
    assert m["metrics"] == {"1": {"accuracy": 0.9}}
    assert m["global_metrics"]["0"]["accuracy"] == 0.5
    assert run_manifest(run_config={}, metrics={})["global_metrics"] == {}


def test_run_manifest_records_a_dirty_tree(tmp_path: Path, monkeypatch) -> None:
    import subprocess

    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "init",
        ],
        check=True,
    )
    (tmp_path / "f.txt").write_text("a")
    subprocess.run(["git", "add", "f.txt"], check=True)
    assert run_manifest(run_config={}, metrics={})["git"]["dirty"] is True


def test_run_manifest_extra_adds_top_level_keys() -> None:
    m = run_manifest(run_config={}, metrics={}, extra={"attacker_outlier_rank": {"6": [1]}})
    assert m["attacker_outlier_rank"] == {"6": [1]}


def test_run_manifest_extra_cannot_overwrite_core_keys() -> None:
    with pytest.raises(ValueError, match="global_metrics"):
        run_manifest(run_config={}, metrics={}, extra={"global_metrics": {}})


def test_run_manifest_dirty_is_unknown_outside_git(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    assert run_manifest(run_config={}, metrics={})["git"]["dirty"] is None


def test_suite_runs_without_git_env() -> None:
    import os

    assert not [k for k in os.environ if k.startswith("GIT_")]
