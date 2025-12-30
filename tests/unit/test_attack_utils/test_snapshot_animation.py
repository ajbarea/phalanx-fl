"""Unit tests for attack snapshot animation module.

Tests GIF animation generation for attack timelines and metrics.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend for testing

from src.attack_utils.snapshot_animation import (
    DEFAULT_DPI,
    DEFAULT_DURATION_PER_FRAME_MS,
    DEFAULT_FPS,
    generate_all_animations,
    save_accuracy_progression_gif,
    save_attack_timeline_gif,
    save_client_comparison_gif,
)


class TestSaveAttackTimelineGif(unittest.TestCase):
    """Test save_attack_timeline_gif function."""

    def test_creates_gif_file(self):
        """Should create a GIF file at the specified path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_timeline.gif"
            attack_timeline = {
                "0": {"1": ["label_flipping"], "2": ["label_flipping"]},
                "1": {"3": ["model_poisoning"]},
            }
            save_attack_timeline_gif(
                attack_timeline=attack_timeline,
                filepath=filepath,
                total_rounds=5,
                total_clients=3,
            )
            self.assertTrue(filepath.exists())

    def test_handles_empty_timeline(self):
        """Should handle empty attack timeline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_empty.gif"
            attack_timeline: dict[str, dict[str, list[str]]] = {}
            save_attack_timeline_gif(
                attack_timeline=attack_timeline,
                filepath=filepath,
                total_rounds=5,
                total_clients=3,
            )
            self.assertTrue(filepath.exists())

    def test_auto_detects_attack_types(self):
        """Should auto-detect attack types if not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_auto_detect.gif"
            attack_timeline = {
                "0": {"1": ["gaussian_noise"]},
                "1": {"2": ["model_poisoning"]},
            }
            # Don't pass attack_types, should auto-detect
            save_attack_timeline_gif(
                attack_timeline=attack_timeline,
                filepath=filepath,
                total_rounds=3,
                total_clients=2,
            )
            self.assertTrue(filepath.exists())

    def test_uses_provided_attack_types(self):
        """Should use provided attack types list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_provided.gif"
            attack_timeline = {"0": {"1": ["label_flipping"]}}
            save_attack_timeline_gif(
                attack_timeline=attack_timeline,
                filepath=filepath,
                total_rounds=2,
                total_clients=1,
                attack_types=["label_flipping", "model_poisoning"],
            )
            self.assertTrue(filepath.exists())

    def test_handles_single_client_single_round(self):
        """Should handle minimal case with single client and round."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_minimal.gif"
            attack_timeline = {"0": {"1": ["gaussian_noise"]}}
            save_attack_timeline_gif(
                attack_timeline=attack_timeline,
                filepath=filepath,
                total_rounds=1,
                total_clients=1,
            )
            self.assertTrue(filepath.exists())

    def test_handles_all_attack_types(self):
        """Should handle all known attack types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_all_types.gif"
            attack_timeline = {
                "0": {"1": ["label_flipping"]},
                "1": {"1": ["gaussian_noise"]},
                "2": {"1": ["model_poisoning"]},
                "3": {"1": ["gradient_scaling"]},
                "4": {"1": ["byzantine_perturbation"]},
                "5": {"1": ["token_replacement"]},
            }
            save_attack_timeline_gif(
                attack_timeline=attack_timeline,
                filepath=filepath,
                total_rounds=2,
                total_clients=6,
            )
            self.assertTrue(filepath.exists())

    def test_gif_file_size_reasonable(self):
        """Generated GIF should have reasonable file size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_size.gif"
            attack_timeline = {"0": {"1": ["label_flipping"]}}
            save_attack_timeline_gif(
                attack_timeline=attack_timeline,
                filepath=filepath,
                total_rounds=3,
                total_clients=2,
            )
            file_size = filepath.stat().st_size
            # Should be at least 1KB but less than 5MB
            self.assertGreater(file_size, 1024)
            self.assertLess(file_size, 5 * 1024 * 1024)


class TestSaveAccuracyProgressionGif(unittest.TestCase):
    """Test save_accuracy_progression_gif function."""

    def test_creates_gif_file(self):
        """Should create a GIF file at the specified path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_accuracy.gif"
            round_metrics = [
                {"round": 1, "accuracy": 0.1},
                {"round": 2, "accuracy": 0.2},
                {"round": 3, "accuracy": 0.3},
            ]
            save_accuracy_progression_gif(
                round_metrics=round_metrics,
                filepath=filepath,
            )
            self.assertTrue(filepath.exists())

    def test_handles_empty_metrics(self):
        """Should handle empty round metrics gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_empty.gif"
            # Should not raise, just log warning
            save_accuracy_progression_gif(
                round_metrics=[],
                filepath=filepath,
            )
            # File may or may not exist, but no exception

    def test_includes_attack_round_shading(self):
        """Should include attack round shading when provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_attacks.gif"
            round_metrics = [
                {"round": 1, "accuracy": 0.1},
                {"round": 2, "accuracy": 0.15},
                {"round": 3, "accuracy": 0.2},
                {"round": 4, "accuracy": 0.25},
            ]
            save_accuracy_progression_gif(
                round_metrics=round_metrics,
                filepath=filepath,
                attack_rounds=[2, 3],
            )
            self.assertTrue(filepath.exists())

    def test_handles_missing_accuracy_key(self):
        """Should handle metrics without 'accuracy' key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_no_accuracy.gif"
            round_metrics: list[dict[str, Any]] = [
                {"round": 1},  # No accuracy
                {"round": 2, "accuracy": 0.2},
            ]
            save_accuracy_progression_gif(
                round_metrics=round_metrics,
                filepath=filepath,
            )
            self.assertTrue(filepath.exists())

    def test_handles_missing_round_key(self):
        """Should handle metrics without 'round' key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_no_round.gif"
            round_metrics: list[dict[str, Any]] = [
                {"accuracy": 0.1},  # No round
                {"accuracy": 0.2},
            ]
            save_accuracy_progression_gif(
                round_metrics=round_metrics,
                filepath=filepath,
            )
            self.assertTrue(filepath.exists())


class TestSaveClientComparisonGif(unittest.TestCase):
    """Test save_client_comparison_gif function."""

    def test_creates_gif_file(self):
        """Should create a GIF file at the specified path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_comparison.gif"
            per_client_metrics = {
                0: [{"round": 1, "accuracy": 0.1}, {"round": 2, "accuracy": 0.2}],
                1: [{"round": 1, "accuracy": 0.15}, {"round": 2, "accuracy": 0.25}],
            }
            save_client_comparison_gif(
                per_client_metrics=per_client_metrics,
                filepath=filepath,
            )
            self.assertTrue(filepath.exists())

    def test_handles_empty_metrics(self):
        """Should handle empty per-client metrics gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_empty.gif"
            # Should not raise, just log warning
            save_client_comparison_gif(
                per_client_metrics={},
                filepath=filepath,
            )
            # File may or may not exist, but no exception

    def test_highlights_malicious_clients(self):
        """Should highlight malicious clients differently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_malicious.gif"
            per_client_metrics = {
                0: [{"round": 1, "accuracy": 0.1}],
                1: [{"round": 1, "accuracy": 0.12}],
                2: [{"round": 1, "accuracy": 0.08}],
            }
            save_client_comparison_gif(
                per_client_metrics=per_client_metrics,
                filepath=filepath,
                malicious_clients=[0, 1],
            )
            self.assertTrue(filepath.exists())

    def test_handles_varying_round_counts(self):
        """Should handle clients with different round counts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_varying.gif"
            per_client_metrics = {
                0: [{"round": 1, "accuracy": 0.1}, {"round": 2, "accuracy": 0.2}],
                1: [{"round": 1, "accuracy": 0.15}],  # Only 1 round
            }
            save_client_comparison_gif(
                per_client_metrics=per_client_metrics,
                filepath=filepath,
            )
            self.assertTrue(filepath.exists())


class TestGenerateAllAnimations(unittest.TestCase):
    """Test generate_all_animations function."""

    def test_generates_timeline_animation(self):
        """Should generate attack timeline animation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            attack_summary = {
                "experiment": {"total_rounds": 3, "total_clients": 2},
                "attack_summary": {"attack_types": ["label_flipping"]},
                "attack_timeline": {"0": {"1": ["label_flipping"]}},
            }
            generated = generate_all_animations(
                output_dir=output_dir,
                attack_summary=attack_summary,
            )
            self.assertGreater(len(generated), 0)
            timeline_path = output_dir / "attack_snapshots_0" / "attack_timeline.gif"
            self.assertTrue(timeline_path.exists())

    def test_generates_accuracy_animation_when_metrics_provided(self):
        """Should generate accuracy animation when round metrics provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            attack_summary = {
                "experiment": {"total_rounds": 2, "total_clients": 1},
                "attack_summary": {"attack_types": [], "rounds_with_attacks": []},
                "attack_timeline": {},
            }
            round_metrics = [
                {"round": 1, "accuracy": 0.1},
                {"round": 2, "accuracy": 0.2},
            ]
            generate_all_animations(
                output_dir=output_dir,
                attack_summary=attack_summary,
                round_metrics=round_metrics,
            )
            accuracy_path = output_dir / "attack_snapshots_0" / "accuracy_progression.gif"
            self.assertTrue(accuracy_path.exists())

    def test_generates_client_comparison_when_metrics_provided(self):
        """Should generate client comparison when per-client metrics provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            attack_summary = {
                "experiment": {"total_rounds": 2, "total_clients": 2},
                "attack_summary": {"attack_types": [], "clients_attacked": []},
                "attack_timeline": {},
            }
            per_client_metrics = {
                0: [{"round": 1, "accuracy": 0.1}],
                1: [{"round": 1, "accuracy": 0.12}],
            }
            generate_all_animations(
                output_dir=output_dir,
                attack_summary=attack_summary,
                per_client_metrics=per_client_metrics,
            )
            comparison_path = output_dir / "attack_snapshots_0" / "client_comparison.gif"
            self.assertTrue(comparison_path.exists())

    def test_creates_snapshots_directory(self):
        """Should create attack_snapshots_N directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            attack_summary = {
                "experiment": {"total_rounds": 1, "total_clients": 1},
                "attack_summary": {"attack_types": []},
                "attack_timeline": {},
            }
            generate_all_animations(
                output_dir=output_dir,
                attack_summary=attack_summary,
            )
            snapshots_dir = output_dir / "attack_snapshots_0"
            self.assertTrue(snapshots_dir.exists())

    def test_uses_strategy_number(self):
        """Should use strategy number in directory name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            attack_summary = {
                "experiment": {"total_rounds": 1, "total_clients": 1},
                "attack_summary": {"attack_types": ["label_flipping"]},
                "attack_timeline": {"0": {"1": ["label_flipping"]}},
            }
            generate_all_animations(
                output_dir=output_dir,
                attack_summary=attack_summary,
                strategy_number=2,
            )
            snapshots_dir = output_dir / "attack_snapshots_2"
            self.assertTrue(snapshots_dir.exists())

    def test_returns_list_of_generated_paths(self):
        """Should return list of all generated file paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            attack_summary = {
                "experiment": {"total_rounds": 2, "total_clients": 1},
                "attack_summary": {
                    "attack_types": ["label_flipping"],
                    "rounds_with_attacks": [1],
                    "clients_attacked": [0],
                },
                "attack_timeline": {"0": {"1": ["label_flipping"]}},
            }
            round_metrics = [{"round": 1, "accuracy": 0.1}]
            per_client_metrics = {0: [{"round": 1, "accuracy": 0.1}]}
            generated = generate_all_animations(
                output_dir=output_dir,
                attack_summary=attack_summary,
                round_metrics=round_metrics,
                per_client_metrics=per_client_metrics,
            )
            self.assertIsInstance(generated, list)
            for path in generated:
                self.assertIsInstance(path, Path)
                self.assertTrue(path.exists())


class TestAnimationDefaults(unittest.TestCase):
    """Test animation configuration defaults."""

    def test_default_fps_value(self):
        """DEFAULT_FPS should be a reasonable value."""
        self.assertIsInstance(DEFAULT_FPS, int)
        self.assertGreater(DEFAULT_FPS, 0)
        self.assertLess(DEFAULT_FPS, 30)

    def test_default_dpi_value(self):
        """DEFAULT_DPI should be a reasonable value."""
        self.assertIsInstance(DEFAULT_DPI, int)
        self.assertGreater(DEFAULT_DPI, 50)
        self.assertLess(DEFAULT_DPI, 300)

    def test_default_duration_value(self):
        """DEFAULT_DURATION_PER_FRAME_MS should be reasonable."""
        self.assertIsInstance(DEFAULT_DURATION_PER_FRAME_MS, int)
        self.assertGreater(DEFAULT_DURATION_PER_FRAME_MS, 100)
        self.assertLess(DEFAULT_DURATION_PER_FRAME_MS, 5000)


if __name__ == "__main__":
    unittest.main()
