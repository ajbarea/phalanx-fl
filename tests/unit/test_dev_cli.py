"""Tests for the cross-platform developer CLI."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from intellifl import dev_cli


def test_run_task_sets_utf8_defaults(monkeypatch) -> None:
    """Child processes should inherit the repo's UTF-8 defaults."""
    captured: dict[str, object] = {}

    def fake_run(command, cwd, env, check):  # type: ignore[no-untyped-def]
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        captured["check"] = check
        return SimpleNamespace(returncode=0)

    monkeypatch.delenv("PYTHONUTF8", raising=False)
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    monkeypatch.setattr(dev_cli.subprocess, "run", fake_run)

    assert dev_cli.run_task("check-env") == 0
    assert captured["cwd"] == dev_cli.PROJECT_ROOT
    assert captured["check"] is False

    env = captured["env"]
    assert isinstance(env, dict)
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["UV_PROJECT_ENVIRONMENT"] == ".venv"


def test_yolo_runs_clean_setup_then_upgrade(monkeypatch) -> None:
    """The composite yolo task should run the three maintenance steps in order."""
    commands: list[list[str]] = []

    def fake_run_process(command: list[str], *, cwd: Path) -> int:
        commands.append(command)
        assert cwd == dev_cli.PROJECT_ROOT
        return 0

    monkeypatch.setattr(dev_cli, "run_process", fake_run_process)

    assert dev_cli.run_task("yolo") == 0
    assert commands == [
        [dev_cli.sys.executable, str(dev_cli.PROJECT_ROOT / "scripts" / "clean_build.py")],
        [dev_cli.sys.executable, str(dev_cli.PROJECT_ROOT / "scripts" / "setup.py")],
        [dev_cli.sys.executable, str(dev_cli.PROJECT_ROOT / "scripts" / "upgrade.py")],
    ]


def test_help_lists_uv_first_commands(capsys) -> None:
    """Help output should advertise the uv-first workflow."""
    dev_cli.print_help()

    output = capsys.readouterr().out
    assert "uv run intellifl-dev <command>" in output
    assert "audit" in output
    assert "check-env" in output
