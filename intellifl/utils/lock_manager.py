import logging
import os
import time
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)


class SimulationLock:
    """A cross-platform file-based lock to ensure sequential simulation execution.

    This lock manages a '.simulation.lock' file in the 'out' directory.
    It includes PID validation to ensure that if a process crashes, the lock
    can be recovered by the next simulation in the queue.
    """

    def __init__(self, lock_dir: Path = Path("out"), lock_name: str = ".simulation.lock"):
        self.lock_dir = lock_dir
        self.lock_file = lock_dir / lock_name
        self.pid = os.getpid()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def acquire(self):
        """Acquires the lock, blocking until it is available."""
        self.lock_dir.mkdir(parents=True, exist_ok=True)

        while True:
            if self._try_acquire():
                logger.debug(f"Lock acquired by PID {self.pid}")
                return

            # Lock is held, check if owner is still alive
            owner_pid = self._get_owner_pid()
            if owner_pid:
                if not self._is_process_running(owner_pid):
                    logger.warning(f"Lock found for dead PID {owner_pid}. Breaking stale lock.")
                    self._break_lock()
                    continue  # Try acquiring again immediately
                else:
                    logger.info(
                        f"Simulation already running (PID {owner_pid}). Waiting in queue..."
                    )

            time.sleep(5)

    def _try_acquire(self) -> bool:
        """Attempt to atomically acquire the lock via directory creation."""
        try:
            lock_path = self.lock_file
            if lock_path.exists():
                return False

            # Write our PID to the lock file
            with lock_path.open("w") as f:
                f.write(str(self.pid))
            return True
        except OSError:
            return False

    def _get_owner_pid(self) -> int | None:
        """Read the PID of the current lock owner."""
        try:
            if self.lock_file.exists():
                with self.lock_file.open("r") as f:
                    content = f.read().strip()
                    return int(content) if content else None
        except (OSError, ValueError):
            pass
        return None

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with the given PID is still active."""
        try:
            return psutil.pid_exists(pid)
        except Exception:
            return False

    def _break_lock(self):
        """Forcefully remove the lock file."""
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
        except OSError:
            pass

    def release(self):
        """Releases the lock so the next simulation can proceed."""
        owner_pid = self._get_owner_pid()
        if owner_pid == self.pid:
            self._break_lock()
            logger.debug(f"Lock released by PID {self.pid}")
        else:
            logger.debug(f"Release called by non-owner PID {self.pid} (Owner: {owner_pid})")
