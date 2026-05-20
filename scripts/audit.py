#!/usr/bin/env python3
"""Security audit for Python and frontend dependencies.

Auto-fixes what can be fixed:
  - Frontend: runs npm audit fix (auto-fixes vulnerabilities)
  - Backend: audits and reports vulnerabilities (auto-fix via dependency updates)

Logs results separately for visibility.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

from logging_utils import setup_logger

backend_logger = setup_logger("backend-audit", "backend-audit.log")
frontend_logger = setup_logger("frontend-audit", "frontend-audit.log")


def parse_skipped(output: str) -> list[str]:
    """Extract skipped package names from pip-audit tabular output."""
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
        if len(parts) >= 2 and any(kw in parts[1] for kw in ("PyPI", "audited", "not found")):
            skipped.append(parts[0])
        else:
            in_table = False
    return skipped


def run_backend_audit() -> int:
    """Run backend security audit using pip-audit or uv audit.

    Returns:
        0 if no vulnerabilities, 1 if vulnerabilities found.
    """
    print("  ▶ Backend audit (Python dependencies)...")
    backend_logger.info("Starting backend audit...")

    # Unpatched-upstream ignore list — review before every release.
    # Each entry's advisory reports "Patched versions: None" or has no fix
    # listed in the pip-audit `Fix Versions` column. When upstream ships a
    # patched release, drop the corresponding entry.
    #
    # CVE-2026-3219 (pip): advisory GHSA-58qw-9mgm-455v updated 2026-04-25.
    # PYSEC-2024-277 (joblib 1.5.3, latest on PyPI 2026-05-20).
    # PYSEC-2026-89 (markdown 3.10.2, latest on PyPI 2026-05-20).
    # PYSEC-2025-211 through PYSEC-2025-218 (transformers): eight advisories
    #   in the same series; still unpatched in transformers 5.9.0 (latest on
    #   PyPI 2026-05-20). Filed against HuggingFace upstream — track via
    #   https://github.com/huggingface/transformers/security/advisories.
    transformers_advisories = [
        f"--ignore-vuln=PYSEC-2025-{n}" for n in range(211, 219)
    ]
    tools = [
        (
            [
                "pip-audit",
                "--ignore-vuln=CVE-2026-3219",
                "--ignore-vuln=PYSEC-2024-277",
                "--ignore-vuln=PYSEC-2026-89",
                *transformers_advisories,
            ],
            "pip-audit",
        ),
        (["uv", "audit"], "uv audit"),
    ]

    for cmd, label in tools:
        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            output = result.stdout + result.stderr
            backend_logger.debug(output.strip())

            skipped = parse_skipped(output)
            passed = result.returncode == 0

            if passed:
                print("    ✓ No vulnerabilities found")
                backend_logger.info("✓ Backend audit passed — no vulnerabilities found")
            else:
                print("    ⚠ Vulnerabilities found (see backend-audit.log)")
                backend_logger.error("Backend audit failed — vulnerabilities detected")
                if output.strip():
                    backend_logger.debug(f"Full output:\n{output.strip()}")

            if skipped:
                print(f"    ℹ {len(skipped)} package(s) skipped: {', '.join(skipped)}")
                backend_logger.info(f"Skipped packages: {', '.join(skipped)}")

            return 0 if passed else 1

        except FileNotFoundError:
            continue

    # No audit tool available
    print("    ⚠ No audit tool available (pip-audit or uv audit)")
    backend_logger.warning("No security audit tool available")
    return 0


def run_frontend_audit() -> int:
    """Run frontend security audit and auto-fix vulnerabilities.

    Returns:
        0 if no remaining vulnerabilities, 1 if vulnerabilities found.
    """
    print("  ▶ Frontend audit (npm dependencies)...")
    frontend_logger.info("Starting frontend audit...")

    frontend_dir = Path("frontend")

    if not frontend_dir.is_dir():
        error_msg = "Frontend directory not found at ./frontend"
        print(f"    ✗ {error_msg}")
        frontend_logger.error(error_msg)
        return 1

    try:
        npm_path = shutil.which("npm")
        if not npm_path:
            raise FileNotFoundError("npm not found in PATH")

        # Run npm audit fix (auto-fixes vulnerabilities)
        frontend_logger.info("Running: npm audit fix")
        result = subprocess.run(
            [npm_path, "audit", "fix"],
            cwd=str(frontend_dir),
            capture_output=True,
            text=True,
            check=False,
        )

        full_output = result.stdout + result.stderr
        frontend_logger.debug(full_output.strip())

        # Parse metrics
        metrics = {
            "packages_audited": 0,
            "vulnerabilities": 0,
            "packages_funding": 0,
        }

        packages_match = re.search(r"audited (\d+) packages?", full_output)
        if packages_match:
            metrics["packages_audited"] = int(packages_match.group(1))

        vuln_match = re.search(r"found (\d+) vulnerabilities?", full_output)
        if vuln_match:
            metrics["vulnerabilities"] = int(vuln_match.group(1))

        funding_match = re.search(r"(\d+) packages? (?:are )?looking for funding", full_output)
        if funding_match:
            metrics["packages_funding"] = int(funding_match.group(1))

        # Display summary
        vuln_count = metrics["vulnerabilities"]
        print("    ✓ npm audit fix" if vuln_count == 0 else "    ⚠ npm audit fix")
        print(f"    Packages audited: {metrics['packages_audited']}")
        if vuln_count > 0:
            print(f"    Remaining vulnerabilities: {vuln_count}")

        frontend_logger.info(f"Packages audited: {metrics['packages_audited']}")
        if vuln_count == 0:
            frontend_logger.info("✓ No vulnerabilities found after fix")
        else:
            frontend_logger.warning(f"Found {vuln_count} remaining vulnerabilities")

        if metrics["packages_funding"] > 0:
            frontend_logger.info(f"Packages looking for funding: {metrics['packages_funding']}")

        return 0 if vuln_count == 0 else 1

    except FileNotFoundError:
        error_msg = "npm not found. Please install Node.js and npm."
        print(f"    ✗ {error_msg}")
        frontend_logger.error(error_msg)
        return 1
    except Exception as e:
        error_msg = f"Frontend audit failed: {e}"
        print(f"    ✗ {error_msg}")
        frontend_logger.error(error_msg)
        return 1


def main() -> int:
    """Run unified security audit for all dependencies.

    Returns:
        0 if all audits passed, 1 if vulnerabilities found.
    """
    print("\n🔒 Security Audit (Unified)")
    print("=" * 60)
    print("Running auto-fixes and security checks...\n")

    backend_status = run_backend_audit()
    print()
    frontend_status = run_frontend_audit()

    print("\n" + "=" * 60)
    if backend_status == 0 and frontend_status == 0:
        print("✓ All security checks passed")
        print("=" * 60 + "\n")
        return 0
    else:
        if frontend_status != 0:
            print("⚠ Frontend: Some vulnerabilities remain (see frontend-audit.log)")
        if backend_status != 0:
            print("⚠ Backend: Vulnerabilities detected (see backend-audit.log)")
        print("=" * 60 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
