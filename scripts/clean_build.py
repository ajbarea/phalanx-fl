#!/usr/bin/env python3
"""Build artifact and cache cleanup utility.

Removes build artifacts, test caches, and temporary files to maintain a clean
development environment. Supports selective cleanup of experiment results via
the --out flag.
"""

import argparse
import shutil
import sys
from pathlib import Path

from logging_utils import setup_logger

logger = setup_logger(__name__, "clean_build.log")


def clean_build(clean_out: bool = False) -> None:
    """Remove build artifacts and cache directories.

    Args:
        clean_out: If True, also clean the out/ directory containing
            experiment results. Preserves .gitkeep file.
    """
    print("\n🧹 IntelliFL Cleanup")
    print("=" * 60)
    logger.info("Starting cleanup...")
    root = Path(".")

    # Close logger handlers before cleaning logs directory
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    cleaned_count = 0
    removed_count = 0

    dirs_to_clear = [
        root / "logs",
        root / "tests" / "logs",
        root / "test-results",
    ]

    print("\n▶ Clearing directories...")
    for d in dirs_to_clear:
        if d.exists():
            for item in d.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            print(f"  ✓ Cleared {d}")
            logger.info(f"Cleaned {d} directory")
            cleaned_count += 1

    dirs_to_remove = [
        root / ".mypy_cache",
        root / ".ruff_cache",
        root / ".mutmut-cache",
        root / "frontend" / "dist",
        root / "site",
        root / ".playwright-mcp",
    ]

    print("\n▶ Removing cache directories...")
    for d in dirs_to_remove:
        if d.exists():
            shutil.rmtree(d)
            print(f"  ✓ Removed {d}")
            logger.info(f"Removed {d} directory")
            removed_count += 1

    patterns_to_remove = [
        ".pytest_cache",
        "__pycache__",
        ".hypothesis",
        "MagicMock",
        "*.egg-info",
    ]

    print("\n▶ Cleaning artifact patterns...")
    for pattern in patterns_to_remove:
        count = 0
        for p in root.rglob(pattern):
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            count += 1
        if count > 0:
            print(f"  ✓ Cleaned {count} {pattern} artifacts")
            logger.info(f"Cleaned {pattern} artifacts")

    files_to_remove = [
        root / ".coverage",
        root / "tests" / ".coverage",
    ]
    for f in root.rglob(".coverage.*"):
        files_to_remove.append(f)
    for f in root.rglob("uv.lock.backup.*"):
        files_to_remove.append(f)

    print("\n▶ Removing coverage files...")
    for f in files_to_remove:
        if f.exists():
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
