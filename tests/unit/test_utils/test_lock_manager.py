"""Unit tests for SimulationLock — cross-platform file lock with PID recovery."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from intellifl.utils.lock_manager import SimulationLock


@pytest.fixture
def lock_dir(tmp_path):
    return tmp_path / "out"


class TestAcquireRelease:
    def test_acquire_creates_lock_file_with_current_pid(self, lock_dir):
        lock = SimulationLock(lock_dir=lock_dir, lock_name=".test.lock")
        lock.acquire()
        try:
            assert lock.lock_file.exists()
            assert lock.lock_file.read_text().strip() == str(os.getpid())
        finally:
            lock.release()

    def test_release_removes_lock_when_owner_matches(self, lock_dir):
        lock = SimulationLock(lock_dir=lock_dir, lock_name=".test.lock")
        lock.acquire()
        lock.release()
        assert not lock.lock_file.exists()

    def test_release_does_nothing_when_owner_differs(self, lock_dir):
        lock = SimulationLock(lock_dir=lock_dir, lock_name=".test.lock")
        lock_dir.mkdir(parents=True, exist_ok=True)
        # Plant a lock file owned by a different PID
        lock.lock_file.write_text("999999")
        lock.release()
        assert lock.lock_file.exists(), "Non-owner release must not delete the file"

    def test_context_manager_acquires_and_releases(self, lock_dir):
        lock = SimulationLock(lock_dir=lock_dir, lock_name=".ctx.lock")
        with lock:
            assert lock.lock_file.exists()
        assert not lock.lock_file.exists()

    def test_acquire_creates_parent_directory(self, tmp_path):
        nested = tmp_path / "deeply" / "nested"
        lock = SimulationLock(lock_dir=nested, lock_name=".test.lock")
        lock.acquire()
        try:
            assert nested.exists()
            assert lock.lock_file.exists()
        finally:
            lock.release()


class TestStaleRecovery:
    def test_breaks_stale_lock_when_owner_pid_is_dead(self, lock_dir):
        lock_dir.mkdir(parents=True, exist_ok=True)
        stale_lock = lock_dir / ".test.lock"
        stale_lock.write_text("999999")  # almost certainly not a live PID

        lock = SimulationLock(lock_dir=lock_dir, lock_name=".test.lock")
        with patch.object(lock, "_is_process_running", return_value=False):
            lock.acquire()
        try:
            # The new lock file should now hold our PID
            assert lock.lock_file.read_text().strip() == str(os.getpid())
        finally:
            lock.release()


class TestInternalHelpers:
    def test_get_owner_pid_returns_none_when_file_missing(self, lock_dir):
        lock = SimulationLock(lock_dir=lock_dir, lock_name=".missing.lock")
        assert lock._get_owner_pid() is None

    def test_get_owner_pid_returns_none_when_file_empty(self, lock_dir):
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock = SimulationLock(lock_dir=lock_dir, lock_name=".empty.lock")
        lock.lock_file.write_text("")
        assert lock._get_owner_pid() is None

    def test_get_owner_pid_returns_none_when_file_garbage(self, lock_dir):
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock = SimulationLock(lock_dir=lock_dir, lock_name=".garbage.lock")
        lock.lock_file.write_text("not-an-int")
        assert lock._get_owner_pid() is None

    def test_is_process_running_for_self_is_true(self, lock_dir):
        lock = SimulationLock(lock_dir=lock_dir)
        assert lock._is_process_running(os.getpid()) is True

    def test_is_process_running_swallows_psutil_errors(self, lock_dir):
        lock = SimulationLock(lock_dir=lock_dir)
        with patch("intellifl.utils.lock_manager.psutil.pid_exists", side_effect=OSError):
            assert lock._is_process_running(123) is False

    def test_break_lock_is_idempotent(self, lock_dir):
        lock = SimulationLock(lock_dir=lock_dir, lock_name=".x.lock")
        lock_dir.mkdir(parents=True, exist_ok=True)
        # File doesn't exist — must not raise
        lock._break_lock()
        # Now create one and break it
        lock.lock_file.write_text("123")
        lock._break_lock()
        assert not lock.lock_file.exists()

    def test_try_acquire_returns_false_when_lock_already_present(self, lock_dir):
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock = SimulationLock(lock_dir=lock_dir, lock_name=".held.lock")
        lock.lock_file.write_text("42")
        assert lock._try_acquire() is False

    def test_try_acquire_swallows_oserror(self, lock_dir):
        lock = SimulationLock(lock_dir=lock_dir, lock_name=".io.lock")
        lock_dir.mkdir(parents=True, exist_ok=True)
        with patch("pathlib.Path.open", side_effect=OSError("disk full")):
            assert lock._try_acquire() is False
