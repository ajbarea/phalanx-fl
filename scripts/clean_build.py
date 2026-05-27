#!/usr/bin/env python3
"""Build artifact and cache cleanup utility.

Removes build artifacts, test caches, and temporary files to maintain a clean
development environment. Supports selective cleanup of experiment results via
the --out flag.
"""

import argparse
import shutil
import sys
import time
from pathlib import Path

from logging_utils import setup_logger

logger = setup_logger(__name__, "clean_build.log")

LOG_ARCHIVE_GLOB = "dev-*-*.log"
LOG_ARCHIVE_MAX_AGE_DAYS = 30


def clean_build(clean_out: bool = False) -> None:
    """Remove build artifacts and cache directories.

    Args:
        clean_out: If True, also clean the out/ directory containing
            experiment results. Preserves .gitkeep file.
    """
    print("\n🧹 Phalanx Cleanup")
    print("=" * 60)
    logger.info("Starting cleanup...")
    root = Path(".")

    # Clearing directories
    dirs_to_clear = [
        root / "test-results",
    ]
    existing_dirs_to_clear = [d for d in dirs_to_clear if d.exists()]
    if existing_dirs_to_clear:
        print("\n▶ Clearing directories...")
        for d in existing_dirs_to_clear:
            for item in d.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                except PermissionError:
                    print(f"  ⚠ Skipped (locked): {item}")
            print(f"  ✓ Cleared {d}")
            logger.info(f"Cleaned {d} directory")

    # Pruning stale dev-runner log archives (keep *-latest.log + recent runs)
    log_dirs = [root / "logs", root / "tests" / "logs"]
    cutoff = time.time() - LOG_ARCHIVE_MAX_AGE_DAYS * 86400
    pruned = 0
    for log_dir in log_dirs:
        if not log_dir.is_dir():
            continue
        for log_file in log_dir.glob(LOG_ARCHIVE_GLOB):
            if log_file.name.endswith("-latest.log"):
                continue
            try:
                if log_file.stat().st_mtime < cutoff:
                    log_file.unlink()
                    pruned += 1
            except (PermissionError, FileNotFoundError):
                pass
    if pruned:
        print("\n▶ Pruning stale log archives...")
        print(f"  ✓ Pruned {pruned} archive(s) older than {LOG_ARCHIVE_MAX_AGE_DAYS} days")
        logger.info(f"Pruned {pruned} stale dev-runner log archives")

    # Removing cache directories
    dirs_to_remove = [
        root / ".mypy_cache",
        root / ".ruff_cache",
        root / ".mutmut-cache",
        root / "frontend" / "dist",
        root / "site",
        root / ".playwright-mcp",
    ]
    existing_dirs_to_remove = [d for d in dirs_to_remove if d.exists()]
    if existing_dirs_to_remove:
        print("\n▶ Removing cache directories...")
        for d in existing_dirs_to_remove:
            shutil.rmtree(d)
            print(f"  ✓ Removed {d}")
            logger.info(f"Removed {d} directory")

    # Cleaning artifact patterns
    patterns_to_remove = [
        ".pytest_cache",
        "__pycache__",
        ".hypothesis",
        "MagicMock",
        "*.egg-info",
    ]
    skip_dirs = {".venv", "node_modules"}
    pattern_results = {}
    for pattern in patterns_to_remove:
        count = 0
        for p in root.rglob(pattern):
            if any(part in skip_dirs for part in p.parts):
                continue
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                count += 1
            except PermissionError:
                print(f"  ⚠ Skipped (locked): {p}")
        if count > 0:
            pattern_results[pattern] = count
    if pattern_results:
        print("\n▶ Cleaning artifact patterns...")
        for pattern, count in pattern_results.items():
            print(f"  ✓ Cleaned {count} {pattern} artifacts")
            logger.info(f"Cleaned {pattern} artifacts")

    # Removing coverage files
    files_to_remove = [
        root / ".coverage",
        root / "tests" / ".coverage",
    ]
    for f in root.rglob(".coverage.*"):
        files_to_remove.append(f)
    for f in root.rglob("uv.lock.backup.*"):
        files_to_remove.append(f)
    coverage_to_remove = [f for f in files_to_remove if f.exists()]
    if coverage_to_remove:
        print("\n▶ Removing coverage files...")
        for f in coverage_to_remove:
            f.unlink()
            print(f"  ✓ Removed {f}")
            logger.info(f"Removed {f}")

    if clean_out:
        out_dir = root / "out"
        if out_dir.exists():
            print("\n▶ Cleaning experiment results...")
            for item in out_dir.iterdir():
                if item.name == ".gitkeep":
                    continue
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            print(f"  ✓ Cleaned {out_dir}")
            logger.info("Cleaned out/ directory")

    print("\n" + "=" * 60)
    print("✓ Cleanup completed successfully")
    print("=" * 60 + "\n")
    logger.info("Cleanup completed successfully")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean build artifacts.")
    parser.add_argument("--out", action="store_true", help="Also clean the out/ directory")
    args = parser.parse_args()
    try:
        clean_build(clean_out=args.out)
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        sys.exit(1)
