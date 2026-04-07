#!/usr/bin/env python3
"""Frontend security audit for npm dependencies.

Runs npm audit fix in the frontend directory and logs results.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

from logging_utils import setup_logger

logger = setup_logger(__name__, "frontend-audit.log")


def parse_npm_audit_output(output: str) -> dict:
    """Parse npm audit output for metrics.

    Args:
        output: The stdout/stderr from npm audit fix

    Returns:
        Dictionary with parsed metrics (packages, vulnerabilities, etc.)
    """
    result = {
        "packages_audited": 0,
        "vulnerabilities": 0,
        "packages_funding": 0,
        "raw_output": output,
    }

    # Try to extract packages audited count
    packages_match = re.search(r"audited (\d+) packages?", output)
    if packages_match:
        result["packages_audited"] = int(packages_match.group(1))

    # Try to extract vulnerabilities count
    vuln_match = re.search(r"found (\d+) vulnerabilities?", output)
    if vuln_match:
        result["vulnerabilities"] = int(vuln_match.group(1))

    # Try to extract packages funding info
    funding_match = re.search(r"(\d+) packages? (?:are )?looking for funding", output)
    if funding_match:
        result["packages_funding"] = int(funding_match.group(1))

    return result


def main() -> int:
    """Run frontend security audit.

    Returns:
        0 if audit passes, 1 if vulnerabilities found or command fails.
    """
    print("\n🔒 Frontend Security Audit")
    print("=" * 60)
    logger.info("Starting frontend security audit...")

    frontend_dir = Path("frontend")

    # Verify frontend directory exists
    if not frontend_dir.is_dir():
        error_msg = "Frontend directory not found at ./frontend"
        print(f"❌ {error_msg}")
        logger.error(error_msg)
        print("=" * 60)
        return 1

    try:
        # Find npm executable
        npm_path = shutil.which("npm")
        if not npm_path:
            raise FileNotFoundError("npm not found in PATH")

        # Run npm audit fix in frontend directory
        logger.info("Running: npm audit fix")
        result = subprocess.run(
            [npm_path, "audit", "fix"],
            cwd=str(frontend_dir),
            capture_output=True,
            text=True,
            check=False,  # Don't raise on non-zero exit
        )

        # Combine stdout and stderr for parsing
        full_output = result.stdout + result.stderr
        logger.debug(full_output.strip())

        # Parse metrics from output
        metrics = parse_npm_audit_output(full_output)

        # Display summary
        vuln_count = metrics["vulnerabilities"]
        print("  ✓ npm audit fix" if vuln_count == 0 else "  ✗ npm audit fix")
        print(f"  Packages audited:  {metrics['packages_audited']}")
        print(f"  Vulnerabilities:   {vuln_count} {'✓' if vuln_count == 0 else '⚠'}")

        if metrics["packages_funding"] > 0:
            print(f"  Packages funding:  {metrics['packages_funding']}")

        logger.info(f"Packages audited: {metrics['packages_audited']}")
        if vuln_count == 0:
            logger.info("✓ No vulnerabilities found")
        else:
            logger.warning(f"Found {vuln_count} vulnerabilities")
        if metrics["packages_funding"] > 0:
            logger.info(f"Packages looking for funding: {metrics['packages_funding']}")

        print("\n" + "=" * 60)

        if vuln_count > 0:
            print(f"✗ {vuln_count} vulnerabilities found")
            print("=" * 60 + "\n")
            logger.error(f"Frontend audit failed: {vuln_count} vulnerabilities")
            return 1
        else:
            print("✓ Frontend is secure")
            print("=" * 60 + "\n")
            logger.info("✓ Frontend security audit passed")
            return 0

    except FileNotFoundError:
        error_msg = "npm not found. Please install Node.js and npm."
        print(f"  ✗ {error_msg}")
        logger.error(error_msg)
        print("\n" + "=" * 60)
        print("✗ Frontend audit failed")
        print("=" * 60 + "\n")
        return 1
    except Exception as e:
        error_msg = f"Frontend audit failed: {e}"
        print(f"  ✗ {error_msg}")
        logger.error(error_msg)
        print("\n" + "=" * 60)
        print("✗ Frontend audit failed")
        print("=" * 60 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
