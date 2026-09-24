"""Suite-wide fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True, scope="session")
def _no_git_env() -> Iterator[None]:
    """Drop ``GIT_*`` so tests that shell out to git act on their own scratch repo.

    A git hook exports ``GIT_DIR`` / ``GIT_INDEX_FILE`` / ``GIT_WORK_TREE``; from a
    worktree ``GIT_DIR`` is absolute, and ``git init`` in ``tmp_path`` would rewrite the
    repository being committed to.
    """
    saved = {k: v for k, v in os.environ.items() if k.startswith("GIT_")}
    for key in saved:
        del os.environ[key]
    yield
    os.environ.update(saved)
