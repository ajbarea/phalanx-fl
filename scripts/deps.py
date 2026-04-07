#!/usr/bin/env python3
"""Display and log dependency tree information.

Shows a formatted summary of the project's dependencies with counts
and groups (main, dev, transitive).
"""

import re
import subprocess
import sys

from logging_utils import setup_logger

logger = setup_logger(__name__, "deps.log")


def extract_package_count(output: str) -> int:
    """Extract total resolved package count from uv tree output.

    Args:
        output: The stdout from uv tree

    Returns:
        Total package count, or 0 if not found
    """
    match = re.search(r"Resolved (\d+) packages?", output)
    return int(match.group(1)) if match else 0


def count_dev_packages(output: str) -> int:
    """Count dev group packages from uv tree output.

    Args:
        output: The stdout from uv tree

    Returns:
        Count of packages marked as (group: dev)
    """
    return output.count("(group: dev)")


def main() -> int:
    """Display dependency tree with summary.

    Returns:
        0 if successful, 1 if command fails.
    """
    print("\n📦 Dependency Tree")
    print("=" * 60)
    logger.info("Starting dependency tree analysis...")

    try:
        # Run uv tree
        logger.info("Running: uv tree")
        result = subprocess.run(
            ["uv", "tree"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )

        output = result.stdout
        stderr = result.stderr

        # Extract package counts from stderr (where uv puts the "Resolved X packages" message)
        total_packages = extract_package_count(stderr) or extract_package_count(output)
        dev_packages = count_dev_packages(output)
        main_packages = total_packages - dev_packages

        if stderr:
            logger.debug(f"stderr: {stderr}")

        # Display summary
        print(f"Total packages: {total_packages} (resolved)")
        logger.info(f"Total packages: {total_packages}")

        print(f"├─ {main_packages} main packages")
        logger.info(f"Main packages: {main_packages}")

        print(f"└─ {dev_packages} dev packages")
        logger.info(f"Dev packages: {dev_packages}")

        print("=" * 60)
        print("\n▶ Dependency Tree:")
        print("=" * 60)

        # Print the tree with indentation
        for line in output.split("\n"):
            if line.strip():
                print(line)
                logger.debug(line)

        print("=" * 60)
        print("✓ Dependency tree generated")
        logger.info("✓ Dependency tree analysis complete")

        return 0

    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to run uv tree: {e}"
        print(f"❌ {error_msg}")
        logger.error(error_msg)
        if e.stdout:
            logger.debug(f"stdout: {e.stdout}")
        if e.stderr:
            logger.debug(f"stderr: {e.stderr}")
        print("=" * 60)
        return 1
    except FileNotFoundError:
        error_msg = "uv not found. Please install uv: https://docs.astral.sh/uv/"
        print(f"❌ {error_msg}")
        logger.error(error_msg)
        print("=" * 60)
        return 1
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        print(f"❌ {error_msg}")
        logger.error(error_msg)
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
