"""Unit tests for the StatusTracker class.

Tests simulation progress tracking via status.json file.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.utils.status_tracker import StatusTracker


class TestStatusTrackerInit(unittest.TestCase):
    """Test StatusTracker initialization."""

    def test_init_creates_instance(self):
        """Should create StatusTracker instance with correct attributes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(
                output_dir=Path(tmpdir),
                total_rounds=10,
                total_strategies=2,
            )
            self.assertEqual(tracker.total_rounds, 10)
            self.assertEqual(tracker.total_strategies, 2)
            self.assertEqual(tracker.current_strategy, 0)
            self.assertEqual(tracker.current_round, 0)
            self.assertIsNone(tracker.started_at)
            self.assertEqual(tracker.status_file, Path(tmpdir) / "status.json")

    def test_init_default_strategies(self):
        """Should default to 1 strategy if not specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(
                output_dir=Path(tmpdir),
                total_rounds=5,
            )
            self.assertEqual(tracker.total_strategies, 1)

    def test_init_stores_pid(self):
        """Should store current process ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), 5)
            self.assertEqual(tracker._pid, os.getpid())


class TestStatusTrackerCalculateProgress(unittest.TestCase):
    """Test progress calculation logic."""

    def test_calculate_progress_at_start(self):
        """Progress should be 0 at start."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.current_round = 0
            tracker.current_strategy = 0
            self.assertEqual(tracker._calculate_progress(), 0.0)

    def test_calculate_progress_midway_single_strategy(self):
        """Progress should be 0.5 at round 5 of 10 with 1 strategy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.current_round = 5
            tracker.current_strategy = 0
            self.assertEqual(tracker._calculate_progress(), 0.5)

    def test_calculate_progress_complete_single_strategy(self):
        """Progress should be 1.0 when all rounds complete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.current_round = 10
            tracker.current_strategy = 0
            self.assertEqual(tracker._calculate_progress(), 1.0)

    def test_calculate_progress_multi_strategy(self):
        """Progress should account for multiple strategies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10, total_strategies=2)
            # First strategy complete, second at round 5
            tracker.current_strategy = 1
            tracker.current_round = 5
            # (1 + 0.5) / 2 = 0.75
            self.assertEqual(tracker._calculate_progress(), 0.75)

    def test_calculate_progress_zero_rounds(self):
        """Should return 0.0 if total_rounds is 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=0)
            self.assertEqual(tracker._calculate_progress(), 0.0)

    def test_calculate_progress_zero_strategies(self):
        """Should return 0.0 if total_strategies is 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10, total_strategies=0)
            tracker.total_strategies = 0  # Force to 0
            self.assertEqual(tracker._calculate_progress(), 0.0)

    def test_calculate_progress_capped_at_one(self):
        """Progress should never exceed 1.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.current_round = 15  # Exceeds total
            self.assertLessEqual(tracker._calculate_progress(), 1.0)


class TestStatusTrackerStart(unittest.TestCase):
    """Test start() method."""

    def test_start_creates_status_file(self):
        """start() should create status.json file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            self.assertTrue(tracker.status_file.exists())

    def test_start_sets_running_status(self):
        """start() should set status to 'running'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["status"], "running")

    def test_start_sets_progress_zero(self):
        """start() should set progress to 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["progress"], 0.0)

    def test_start_includes_pid(self):
        """start() should include process ID in status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["pid"], os.getpid())

    def test_start_sets_started_at(self):
        """start() should set started_at timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            self.assertIsNotNone(tracker.started_at)
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertIn("started_at", status)


class TestStatusTrackerUpdateRound(unittest.TestCase):
    """Test update_round() method."""

    def test_update_round_updates_current_round(self):
        """update_round() should update current_round attribute."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            tracker.update_round(5)
            self.assertEqual(tracker.current_round, 5)

    def test_update_round_updates_status_file(self):
        """update_round() should update status.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            tracker.update_round(3)
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["current_round"], 3)

    def test_update_round_updates_progress(self):
        """update_round() should update progress in status.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            tracker.update_round(5)
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["progress"], 0.5)


class TestStatusTrackerNextStrategy(unittest.TestCase):
    """Test next_strategy() method."""

    def test_next_strategy_increments_counter(self):
        """next_strategy() should increment current_strategy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10, total_strategies=3)
            tracker.start()
            tracker.next_strategy()
            self.assertEqual(tracker.current_strategy, 1)

    def test_next_strategy_resets_round(self):
        """next_strategy() should reset current_round to 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10, total_strategies=3)
            tracker.start()
            tracker.update_round(5)
            tracker.next_strategy()
            self.assertEqual(tracker.current_round, 0)

    def test_next_strategy_updates_status_file(self):
        """next_strategy() should update status.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10, total_strategies=3)
            tracker.start()
            tracker.next_strategy()
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["current_strategy"], 1)
            self.assertEqual(status["current_round"], 0)


class TestStatusTrackerComplete(unittest.TestCase):
    """Test complete() method."""

    def test_complete_sets_completed_status(self):
        """complete() should set status to 'completed'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            tracker.complete()
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["status"], "completed")

    def test_complete_sets_progress_one(self):
        """complete() should set progress to 1.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            tracker.complete()
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["progress"], 1.0)

    def test_complete_includes_completed_at(self):
        """complete() should include completed_at timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            tracker.complete()
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertIn("completed_at", status)


class TestStatusTrackerFail(unittest.TestCase):
    """Test fail() method."""

    def test_fail_sets_failed_status(self):
        """fail() should set status to 'failed'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            tracker.fail()
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["status"], "failed")

    def test_fail_includes_error_message(self):
        """fail() should include error message if provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            tracker.fail("Test error message")
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["error"], "Test error message")

    def test_fail_includes_failed_at(self):
        """fail() should include failed_at timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            tracker.fail()
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertIn("failed_at", status)

    def test_fail_preserves_progress(self):
        """fail() should preserve current progress."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            tracker.update_round(5)
            tracker.fail()
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["progress"], 0.5)


class TestStatusTrackerStop(unittest.TestCase):
    """Test stop() method."""

    def test_stop_sets_stopped_status(self):
        """stop() should set status to 'stopped'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            tracker.stop()
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["status"], "stopped")

    def test_stop_includes_stopped_at(self):
        """stop() should include stopped_at timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            tracker.stop()
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertIn("stopped_at", status)

    def test_stop_preserves_progress(self):
        """stop() should preserve current progress."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker.start()
            tracker.update_round(3)
            tracker.stop()
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["progress"], 0.3)


class TestStatusTrackerWriteStatus(unittest.TestCase):
    """Test _write_status() method."""

    def test_write_status_adds_timestamp(self):
        """_write_status() should add updated_at timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker._write_status({"status": "test"})
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertIn("updated_at", status)

    def test_write_status_atomic_write(self):
        """_write_status() should use atomic write via temp file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            tracker._write_status({"status": "first"})
            tracker._write_status({"status": "second"})
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["status"], "second")

    @patch("builtins.open", side_effect=PermissionError("Access denied"))
    def test_write_status_handles_error(self, mock_open):
        """_write_status() should handle write errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=10)
            # Should not raise, just log warning
            tracker._write_status({"status": "test"})


class TestStatusTrackerIntegration(unittest.TestCase):
    """Integration tests for full workflow."""

    def test_full_simulation_lifecycle(self):
        """Test complete simulation lifecycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = StatusTracker(Path(tmpdir), total_rounds=5, total_strategies=2)

            tracker.start()
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["status"], "running")
            self.assertEqual(status["progress"], 0.0)

            for round_num in range(1, 6):
                tracker.update_round(round_num)

            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["progress"], 0.5)

            tracker.next_strategy()

            for round_num in range(1, 6):
                tracker.update_round(round_num)

            tracker.complete()
            with open(tracker.status_file) as f:
                status = json.load(f)
            self.assertEqual(status["status"], "completed")
            self.assertEqual(status["progress"], 1.0)


if __name__ == "__main__":
    unittest.main()
