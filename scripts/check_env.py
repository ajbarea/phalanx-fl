#!/usr/bin/env python3
"""Check environment for required tools."""

import subprocess
import sys

from logging_utils import setup_logger

logger = setup_logger(__name__, "check_env.log")


def check_tool(name: str, cmd: list[str]) -> bool:
    """Check if a tool is available and log its version.

    Args:
        name: Tool name for logging.
        cmd: Command to execute.

    Returns:
        True if tool is available (or optional), False if required tool is missing.
    """
    try:
        result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
        logger.info(f"✓ {name}: {result}")
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        if name == "Docker":
            logger.info(f"⊘ {name} not found (optional)")
            return True  # Docker is optional
        logger.error(f"✗ {name} not found")
        return False


def main() -> int:
    """Main check function.

    Returns:
        0 if all required tools are available, 1 otherwise.
    """
    print("\n✓ Environment Check")
    print("=" * 60)
    logger.info("Checking environment...")
    checks = [
        ("uv", ["uv", "--version"]),
        ("Python", ["python", "--version"]),
        ("Docker", ["docker", "--version"]),
    ]

    results = []
    for name, cmd in checks:
        try:
            result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
            print(f"  ✓ {name}: {result}")
            logger.info(f"✓ {name}: {result}")
            results.append(True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            if name == "Docker":
                print(f"  ⊘ {name}: not found (optional)")
                logger.info(f"⊘ {name} not found (optional)")
                results.append(True)  # Docker is optional
            else:
                print(f"  ✗ {name}: not found")
                logger.error(f"✗ {name} not found")
                results.append(False)

    all_ok = all(results)

    print("=" * 60)
    if all_ok:
        print("✓ All required tools available\n")
        logger.info("Environment check passed")
        return 0
    else:
        print("✗ Some required tools missing\n")
        logger.error("Environment check failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
