#!/usr/bin/env python3
"""Cross-platform wrapper for experiment_runner.py that handles PYTHONPATH automatically."""

import os
import subprocess
import sys
from pathlib import Path


def main():
    """Run experiment_runner with proper PYTHONPATH."""
    # Get the directory where this script is located (project root)
    script_dir = Path(__file__).parent.resolve()
    
    # Set PYTHONPATH to project root
    env = os.environ.copy()
    env["PYTHONPATH"] = str(script_dir)
    
    # Find Python executable
    # Priority: 1) venv, 2) current Python
    venv_paths = [
        script_dir / ".venv" / "Scripts" / "python.exe",  # Windows
        script_dir / ".venv" / "bin" / "python",          # Unix
    ]
    
    python_exe = sys.executable  # Default to current Python
    for venv_path in venv_paths:
        if venv_path.exists():
            python_exe = str(venv_path)
            break
    
    # Build command
    runner_script = script_dir / "tests" / "scripts" / "experiment_runner.py"
    cmd = [python_exe, str(runner_script)] + sys.argv[1:]
    
    # Run the experiment runner
    try:
        result = subprocess.run(cmd, env=env)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"Error running experiment runner: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
