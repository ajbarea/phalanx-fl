"""Shared runtime for the IntelliFL developer workflow.

Provides the primitives that every `intellifl-dev` invocation uses:

- `SessionLog` — dual-sink logger that writes human-readable output to the
  console and a plain, timestamped, ANSI-stripped copy to
  `logs/dev-latest.log` + an archive at `logs/dev-<ts>-<cmd>.log`.
- `run()` — streaming subprocess wrapper that merges stderr into stdout and
  raises `StepFailedError` on non-zero exit.
- `StepFailedError` — typed exception carrying the failing command and rc.
- `fix_and_check()` — run auto-fixers first, then strict checks, and return
  the list of still-failing check labels.
- ANSI color constants with graceful fallback (`NO_COLOR`, non-TTY).

The session archive is what `/aj-audit` reads: a header with tool versions
and git state, per-line timestamps, per-step exit codes, and a SUMMARY
block at the end.
"""

from __future__ import annotations

import atexit
import contextlib
import datetime as _dt
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _color_enabled() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


_USE_COLOR = _color_enabled()
C_BOLD = "\033[1m" if _USE_COLOR else ""
C_DIM = "\033[2m" if _USE_COLOR else ""
C_RED = "\033[31m" if _USE_COLOR else ""
C_GREEN = "\033[32m" if _USE_COLOR else ""
C_YELLOW = "\033[33m" if _USE_COLOR else ""
C_CYAN = "\033[36m" if _USE_COLOR else ""
C_RESET = "\033[0m" if _USE_COLOR else ""


@dataclass(frozen=True)
class StepRecord:
    name: str
    rc: int
    elapsed: float


class SessionLog:
    """Tee logger for a single `intellifl-dev` invocation.

    The handle intentionally outlives `open()` (one file per session), so a
    context-manager pattern doesn't fit — atexit closes it instead.
    """

    def __init__(self) -> None:
        self.file: IO[str] | None = None
        self.latest_path: Path | None = None
        self.archive_path: Path | None = None
        self.started = time.monotonic()
        self.step_stack: list[str] = []
        self.steps: list[StepRecord] = []

    def open(self, command: str) -> None:
        LOGS_DIR.mkdir(exist_ok=True)
        ts = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
        self.latest_path = LOGS_DIR / "dev-latest.log"
        self.archive_path = LOGS_DIR / f"dev-{ts}-{command}.log"
        self.file = open(self.latest_path, "w", encoding="utf-8", buffering=1)  # noqa: SIM115
        atexit.register(self.close)

    def close(self) -> None:
        if self.file and not self.file.closed:
            try:
                self.file.flush()
                if self.latest_path and self.archive_path:
                    with contextlib.suppress(OSError):
                        shutil.copy2(self.latest_path, self.archive_path)
            finally:
                self.file.close()

    def _write(self, line: str) -> None:
        if self.file and not self.file.closed:
            self.file.write(ANSI_RE.sub("", line))
            if not line.endswith("\n"):
                self.file.write("\n")

    def event(self, level: str, msg: str) -> None:
        """Structured script-level event (not subprocess output)."""
        ts = _dt.datetime.now().isoformat(timespec="milliseconds")
        ctx = "/".join(self.step_stack) or "-"
        self._write(f"[{ts}] [{level:<5}] [{ctx}] {msg}")

    def raw(self, text: str) -> None:
        """Raw subprocess output (prefixed but not level-tagged)."""
        ts = _dt.datetime.now().isoformat(timespec="milliseconds")
        ctx = "/".join(self.step_stack) or "-"
        for line in text.splitlines() or [""]:
            self._write(f"[{ts}] [OUT  ] [{ctx}] {line}")

    def push_step(self, name: str) -> None:
        self.step_stack.append(name)
        self.event("STEP", f"enter {name}")

    def pop_step(self, name: str, *, rc: int, elapsed: float) -> None:
        self.event("STEP", f"exit  {name} rc={rc} elapsed={elapsed:.2f}s")
        self.steps.append(StepRecord(name=name, rc=rc, elapsed=elapsed))
        if self.step_stack and self.step_stack[-1] == name:
            self.step_stack.pop()

    def session_header(self, command: str, argv: Sequence[str]) -> None:
        def capture(cmd: Sequence[str]) -> str:
            try:
                out = subprocess.run(
                    list(cmd),
                    cwd=str(PROJECT_ROOT),
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return (
                    (out.stdout or out.stderr).strip().splitlines()[0]
                    if (out.stdout or out.stderr)
                    else ""
                )
            except (OSError, subprocess.TimeoutExpired):
                return ""

        git_sha = capture(["git", "rev-parse", "--short", "HEAD"]) or "unknown"
        git_branch = capture(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
        git_dirty = capture(["git", "status", "--porcelain"])
        uv_ver = capture(["uv", "--version"])

        header = [
            "=" * 78,
            "intellifl-dev — session log",
            "=" * 78,
            f"started    : {_dt.datetime.now().isoformat(timespec='seconds')}",
            f"command    : {command}",
            f"argv       : {' '.join(argv)}",
            f"cwd        : {PROJECT_ROOT}",
            f"platform   : {platform.platform()}",
            f"python     : {sys.version.split()[0]} ({sys.executable})",
            f"uv         : {uv_ver or 'not found'}",
            f"git branch : {git_branch}",
            f"git sha    : {git_sha}",
            f"git dirty  : {'yes' if git_dirty else 'no'}",
            "=" * 78,
            "",
            "# Log format: [ISO-timestamp] [LEVEL] [step/path] message",
            "# LEVELS: INFO, STEP, WARN, ERROR, OUT (subprocess stdout+stderr merged)",
            "# See the SUMMARY block at the bottom for per-step exit codes.",
            "",
        ]
        for line in header:
            self._write(line)

    def session_footer(self, overall_rc: int) -> None:
        elapsed = time.monotonic() - self.started
        failed = [s for s in self.steps if s.rc != 0]
        lines = [
            "",
            "=" * 78,
            "SUMMARY",
            "=" * 78,
            f"total elapsed : {elapsed:.2f}s",
            f"steps run     : {len(self.steps)}",
            f"steps failed  : {len(failed)}",
            f"overall rc    : {overall_rc}",
            "",
            "per-step:",
        ]
        for s in self.steps:
            mark = "PASS" if s.rc == 0 else "FAIL"
            lines.append(f"  {mark}  rc={s.rc:<3} {s.elapsed:>6.2f}s  {s.name}")
        if failed:
            lines += [
                "",
                "DEBUG HINTS",
                "-----------",
                "Grep this log for the failing step name to find its subprocess output.",
                "Each [OUT  ] line is merged stdout+stderr, tagged with its step.",
                "rc=127 means the binary was not on PATH.",
            ]
        lines += ["=" * 78, ""]
        for line in lines:
            self._write(line)


# Process-wide session singleton. Tests and tooling that want a private log
# can construct their own SessionLog; `LOG` is what `dev_cli.py` and the
# shared `run()` helper default to.
LOG = SessionLog()


class StepFailedError(RuntimeError):
    """Raised by `run()` when a subprocess exits non-zero with check=True."""

    def __init__(self, cmd: Sequence[str], returncode: int) -> None:
        super().__init__(f"{' '.join(cmd)} exited with {returncode}")
        self.cmd = list(cmd)
        self.returncode = returncode


def print_header(title: str) -> None:
    print(f"\n{C_BOLD}{C_CYAN}== {title} =={C_RESET}", flush=True)
    LOG.event("INFO", f"=== {title} ===")


def print_step(cmd: Sequence[str], *, label: str | None = None) -> None:
    prefix = f"{C_DIM}$ {C_RESET}"
    printed = " ".join(cmd)
    tag = f" {C_DIM}({label}){C_RESET}" if label else ""
    print(f"{prefix}{printed}{tag}", flush=True)


def _run_streamed(
    cmd: Sequence[str],
    *,
    check: bool,
    label: str | None,
    cwd: Path | None,
    env: dict[str, str] | None,
    capture: bool,
) -> tuple[int, str]:
    step_label = label or " ".join(cmd)
    print_step(cmd, label=label)
    LOG.push_step(step_label)
    LOG.event("INFO", f"cmd: {' '.join(cmd)}")
    started = time.monotonic()
    buf: list[str] = []
    try:
        proc = subprocess.Popen(
            list(cmd),
            cwd=str(cwd or PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            env=env,
        )
    except FileNotFoundError as exc:
        LOG.event("ERROR", f"binary not found: {cmd[0]}")
        LOG.pop_step(step_label, rc=127, elapsed=time.monotonic() - started)
        raise StepFailedError(cmd, 127) from exc

    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            LOG.raw(line.rstrip("\n"))
            if capture:
                buf.append(line)
    finally:
        rc = proc.wait()

    elapsed = time.monotonic() - started
    LOG.pop_step(step_label, rc=rc, elapsed=elapsed)
    if rc != 0:
        LOG.event("ERROR" if check else "WARN", f"exit {rc} after {elapsed:.2f}s")
    if check and rc != 0:
        raise StepFailedError(cmd, rc)
    return rc, "".join(buf)


def run(
    cmd: Sequence[str],
    *,
    check: bool = True,
    label: str | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> int:
    """Run a command, streaming stdout/stderr to console + session log.

    stderr is merged into stdout so ordering matches what a human saw on screen.
    Missing-binary failures are surfaced as rc=127.
    """
    rc, _ = _run_streamed(cmd, check=check, label=label, cwd=cwd, env=env, capture=False)
    return rc


def run_capture(
    cmd: Sequence[str],
    *,
    check: bool = False,
    label: str | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Like `run()`, but also buffers the merged stdout+stderr and returns it.

    Use when the caller needs to parse tool output (e.g. pytest's summary
    line) without losing the live-streaming / session-logging behaviour.
    Defaults to `check=False` because capture callers almost always want to
    inspect output regardless of rc.
    """
    return _run_streamed(cmd, check=check, label=label, cwd=cwd, env=env, capture=True)


def summary(title: str, failures: Sequence[str]) -> None:
    print(f"\n{C_BOLD}{title}{C_RESET}")
    LOG.event("INFO", title)
    if failures:
        print(f"  {C_RED}{len(failures)} check(s) still failing:{C_RESET}")
        for f in failures:
            print(f"    - {f}")
            LOG.event("ERROR", f"still failing: {f}")
    else:
        print(f"  {C_GREEN}all checks passed{C_RESET}")
        LOG.event("INFO", "all checks passed")


def fix_and_check(
    section: str,
    fixers: Sequence[tuple[str, Sequence[str]]],
    checks: Sequence[tuple[str, Sequence[str]]],
    *,
    fixer_cwd: Callable[[str], Path | None] | None = None,
    check_cwd: Callable[[str], Path | None] | None = None,
) -> list[str]:
    """Run fixers (best-effort), then checks (strict). Return list of failures.

    `fixer_cwd` / `check_cwd`, if provided, map a step label to a working
    directory — used by the frontend sub-step that must run inside
    `frontend/`.
    """
    print_header(section)
    print(f"{C_BOLD}-> fix pass{C_RESET}")
    for label, cmd in fixers:
        cwd = fixer_cwd(label) if fixer_cwd else None
        try:
            run(cmd, label=label, cwd=cwd)
        except StepFailedError as exc:
            # Fixers may legitimately return non-zero when nothing can be fixed.
            print(
                f"{C_YELLOW}  warn: fixer '{label}' exited {exc.returncode} "
                f"(continuing to check pass){C_RESET}",
            )
    print(f"\n{C_BOLD}-> check pass{C_RESET}")
    failures: list[str] = []
    for label, cmd in checks:
        cwd = check_cwd(label) if check_cwd else None
        try:
            run(cmd, label=label, cwd=cwd)
            print(f"{C_GREEN}  pass{C_RESET} {label}")
        except StepFailedError:
            print(f"{C_RED}  fail{C_RESET} {label}")
            failures.append(label)
    return failures
