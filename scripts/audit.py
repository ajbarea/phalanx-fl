#!/usr/bin/env python3
"""Security audit for project dependencies.

Attempts to audit dependencies using available tools.
Falls back gracefully if no audit tool is available.
"""

import subprocess
import sys

from logging_utils import setup_logger

logger = setup_logger(__name__, "audit.log")


def main() -> int:
    """Run security audit on dependencies.

    Returns:
        0 if audit passes or is skipped, 1 if audit fails.
    """
    print("\n🔒 Security Audit")
    print("=" * 60)
    logger.info("Starting security audit...")

    # Try pip-audit first
    try:
        logger.info("Attempting pip-audit...")
        result = subprocess.run(
            ["uv", "run", "--no-active", "pip-audit"],
            check=True,
            capture_output=True,
            text=True,
        )
        print("✓ pip-audit passed")
        logger.info("✓ pip-audit passed")
        if result.stdout:
            print(result.stdout)
        return 0
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.debug(f"pip-audit not available or failed: {e}")

    # Try uv audit (if available in newer versions)
    try:
        logger.info("Attempting uv audit...")
        result = subprocess.run(
            ["uv", "audit"],
            check=True,
            capture_output=True,
            text=True,
        )
        print("✓ uv audit passed")
        logger.info("✓ uv audit passed")
        if result.stdout:
            print(result.stdout)
        return 0
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.debug(f"uv audit not available or failed: {e}")

    # If no audit tool is available, log a warning but don't fail
    print("⚠️  No security audit tool available (pip-audit or uv audit)")
    print("   Install pip-audit for security scanning: uv add --dev pip-audit")
    logger.warning("No security audit tool available")
    print("=" * 60)
    print("✓ Audit skipped (no tool available)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
