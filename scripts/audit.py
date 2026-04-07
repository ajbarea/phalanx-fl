#!/usr/bin/env python3
"""Security audit for project dependencies.

Attempts to audit dependencies using pip-audit, falling back to uv audit.
Skipped packages (e.g. local packages not on PyPI) are reported cleanly.
"""

import subprocess
import sys

from logging_utils import setup_logger

logger = setup_logger(__name__, "audit.log")


def parse_skipped(output: str) -> list[str]:
    """Extract skipped package names from pip-audit tabular output.

    Args:
        output: Combined stdout/stderr from pip-audit.

    Returns:
        List of skipped package names.
    """
    skipped = []
    in_table = False
    for line in output.splitlines():
        if "Name" in line and "Skip Reason" in line:
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("-"):
            continue
        if not line.strip():
            in_table = False
            continue
        parts = line.split(None, 1)
        # Only treat as a table entry if the reason contains skip-specific keywords
        if len(parts) >= 2 and any(kw in parts[1] for kw in ("PyPI", "audited", "not found")):
            skipped.append(parts[0])
        else:
            in_table = False
    return skipped


def run_audit(cmd: list[str], label: str) -> tuple[bool | None, str]:
    """Run an audit command and return (passed, full_output).

    Args:
        cmd: Command to run.
        label: Display label for logging.

    Returns:
        (True if passed, False if vulnerabilities found, None if not available), output string.
    """
    print(f"  ▶ Running {label}...")
    logger.info(f"Running: {label}")
    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        output = result.stdout + result.stderr
        logger.debug(output.strip())
        return result.returncode == 0, output
    except FileNotFoundError:
        logger.debug(f"{label} not available")
        return None, ""


def main() -> int:
    """Run security audit on dependencies.

    Returns:
        0 if audit passes or is skipped, 1 if vulnerabilities are found.
    """
    print("\n🔒 Security Audit")
    print("=" * 60)
    logger.info("Starting security audit...")

    # Try pip-audit first, fall back to uv audit
    tools = [
        (["pip-audit"], "pip-audit"),
        (["uv", "audit"], "uv audit"),
    ]

    for cmd, label in tools:
        passed, output = run_audit(cmd, label)

        if passed is None:
            continue  # tool not available, try next

        skipped = parse_skipped(output)

        if passed:
            print("  ✓ No vulnerabilities found")
            logger.info("✓ Audit passed — no vulnerabilities found")
        else:
            print("  ✗ Vulnerabilities found")
            logger.error("Audit failed — vulnerabilities detected")
            if output.strip():
                logger.debug(f"Full output:\n{output.strip()}")

        if skipped:
            print(f"  ⚠  {len(skipped)} package(s) skipped (not on PyPI): {', '.join(skipped)}")
            logger.info(f"Skipped packages: {', '.join(skipped)}")

        print("\n" + "=" * 60)
        if passed:
            print("✓ Audit passed")
        else:
            print("✗ Audit failed")
        print("=" * 60 + "\n")
        logger.info("Security audit complete")
        return 0 if passed else 1

    # No audit tool available
    print("  ⚠  No audit tool available (pip-audit or uv audit)")
    print("     Install pip-audit: uv add --dev pip-audit")
    logger.warning("No security audit tool available")
    print("\n" + "=" * 60)
    print("⚠  Audit skipped")
    print("=" * 60 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
