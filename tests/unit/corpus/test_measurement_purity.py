"""The measurement modules must stay runnable without a GPU stack."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

_HEAVY = {"torch", "transformers", "peft", "datasets", "flwr"}
_MEASUREMENT = ("score.py", "stats.py", "contamination.py")
_CORPUS = Path(__file__).resolve().parents[3] / "phalanx" / "corpus"


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("module", _MEASUREMENT)
def test_measurement_modules_import_no_gpu_stack(module: str) -> None:
    path = _CORPUS / module
    assert path.is_file(), f"{path} should exist"
    offenders = _imported_roots(path) & _HEAVY
    assert not offenders, f"{module} imports {sorted(offenders)}; plan C supplies these inputs"


def test_importing_the_measurement_modules_pulls_in_no_gpu_stack() -> None:
    # A fresh interpreter, because sys.modules in this one is already polluted by the
    # rest of the suite. Checking it in-process would pass or fail on test ordering.
    probe = (
        "import sys\n"
        "import phalanx.corpus.score, phalanx.corpus.stats, phalanx.corpus.contamination\n"
        f"heavy = sorted({sorted(_HEAVY)!r})\n"
        "print(','.join(m for m in heavy if m in sys.modules))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        cwd=_CORPUS.parents[1],
        check=True,
    )
    assert result.stdout.strip() == "", f"measurement imports pulled in {result.stdout.strip()}"
