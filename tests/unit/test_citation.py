"""Validate the repository CITATION.cff software-citation metadata.

Guards that the citation stays valid CFF 1.2.0, cites Phalanx / AJ Barea, and
never regresses to the pre-de-fork upstream attribution.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "CITATION.cff").exists() and (parent / "pyproject.toml").exists():
            return parent
    raise AssertionError("repo root with CITATION.cff not found")


def test_citation_cff_valid_and_cites_phalanx():
    cff_path = _repo_root() / "CITATION.cff"
    cff = yaml.safe_load(cff_path.read_text())

    assert cff["cff-version"] == "1.2.0"
    assert cff["message"]
    assert "Phalanx" in cff["title"]
    assert cff["type"] == "software"
    assert any(a.get("family-names") == "Barea" for a in cff["authors"])
    assert "ajbarea/phalanx-fl" in cff["repository-code"]

    # Pre-de-fork upstream attribution must not regress in.
    assert "dmitrykoro" not in cff_path.read_text().lower()
