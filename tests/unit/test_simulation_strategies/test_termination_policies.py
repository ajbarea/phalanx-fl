"""Unit tests for TerminationHandler and TerminationPolicy.

Pure-logic tests of the policy decision matrix; no Flower or Ray dependencies.
"""

from __future__ import annotations

import logging
from unittest.mock import Mock

import pytest

from intellifl.simulation_strategies.termination_policies import (
    TerminationHandler,
    TerminationPolicy,
)


class TestTerminationPolicyEnum:
    def test_string_values(self):
        assert TerminationPolicy.GRACEFUL.value == "graceful"
        assert TerminationPolicy.STRICT.value == "strict"
        assert TerminationPolicy.ADAPTIVE.value == "adaptive"

    def test_constructible_from_string(self):
        assert TerminationPolicy("strict") is TerminationPolicy.STRICT


class TestHandlerInit:
    def test_accepts_string_policy_and_normalizes(self):
        h = TerminationHandler(policy="graceful", min_clients_threshold=5)
        assert h.policy is TerminationPolicy.GRACEFUL

    def test_accepts_enum_policy_directly(self):
        h = TerminationHandler(policy=TerminationPolicy.STRICT, min_clients_threshold=3)
        assert h.policy is TerminationPolicy.STRICT

    def test_default_min_ratio_is_thirty_percent(self):
        h = TerminationHandler(policy=TerminationPolicy.ADAPTIVE, min_clients_threshold=1)
        assert h.min_ratio == 0.3

    def test_initial_state_clean(self):
        h = TerminationHandler(policy=TerminationPolicy.GRACEFUL, min_clients_threshold=5)
        assert h.termination_triggered is False
        assert h.termination_round is None
        assert h.termination_reason == ""

    def test_uses_module_logger_when_none_provided(self):
        h = TerminationHandler(policy=TerminationPolicy.GRACEFUL, min_clients_threshold=5)
        assert isinstance(h.logger, logging.Logger)

    def test_uses_provided_logger(self):
        custom = logging.getLogger("custom-test-logger")
        h = TerminationHandler(
            policy=TerminationPolicy.GRACEFUL, min_clients_threshold=5, logger=custom
        )
        assert h.logger is custom

    def test_invalid_policy_string_raises(self):
        with pytest.raises(ValueError):
            TerminationHandler(policy="aggressive", min_clients_threshold=5)


class TestStrictPolicy:
    def test_terminates_when_below_threshold(self):
        h = TerminationHandler(
            policy=TerminationPolicy.STRICT, min_clients_threshold=5, logger=Mock()
        )
        stop, reason = h.should_terminate(
            available_clients=4, total_clients=10, round_num=3, removed_count=6
        )
        assert stop is True
        assert "STRICT policy" in reason
        assert "minimum 5 required" in reason
        assert h.termination_triggered is True
        assert h.termination_round == 3

    def test_continues_when_at_threshold(self):
        h = TerminationHandler(policy=TerminationPolicy.STRICT, min_clients_threshold=5)
        stop, reason = h.should_terminate(
            available_clients=5, total_clients=10, round_num=2, removed_count=5
        )
        assert stop is False
        assert reason == ""
        assert h.termination_triggered is False

    def test_continues_when_above_threshold(self):
        h = TerminationHandler(policy=TerminationPolicy.STRICT, min_clients_threshold=5)
        stop, _ = h.should_terminate(
            available_clients=10, total_clients=10, round_num=1, removed_count=0
        )
        assert stop is False


class TestGracefulPolicy:
    def test_terminates_only_when_zero_clients(self):
        h = TerminationHandler(
            policy=TerminationPolicy.GRACEFUL, min_clients_threshold=5, logger=Mock()
        )
        stop, reason = h.should_terminate(
            available_clients=0, total_clients=10, round_num=7, removed_count=10
        )
        assert stop is True
        assert "No clients available" in reason
        assert h.termination_round == 7

    def test_warns_below_threshold_but_continues(self):
        mock_logger = Mock()
        h = TerminationHandler(
            policy=TerminationPolicy.GRACEFUL, min_clients_threshold=5, logger=mock_logger
        )
        stop, reason = h.should_terminate(
            available_clients=2, total_clients=10, round_num=4, removed_count=8
        )
        assert stop is False
        assert reason == ""
        mock_logger.warning.assert_called_once()
        warn_msg = mock_logger.warning.call_args.args[0]
        assert "Below minimum threshold" in warn_msg
        assert "GRACEFUL policy" in warn_msg

    def test_no_warning_when_above_threshold(self):
        mock_logger = Mock()
        h = TerminationHandler(
            policy=TerminationPolicy.GRACEFUL, min_clients_threshold=5, logger=mock_logger
        )
        stop, _ = h.should_terminate(
            available_clients=8, total_clients=10, round_num=1, removed_count=2
        )
        assert stop is False
        mock_logger.warning.assert_not_called()


class TestAdaptivePolicy:
    def test_terminates_below_ratio_threshold(self):
        # 30% of 10 = 3, so 2 available -> terminate
        h = TerminationHandler(
            policy=TerminationPolicy.ADAPTIVE,
            min_clients_threshold=1,
            min_clients_ratio=0.3,
            logger=Mock(),
        )
        stop, reason = h.should_terminate(
            available_clients=2, total_clients=10, round_num=5, removed_count=8
        )
        assert stop is True
        assert "ADAPTIVE policy" in reason
        assert "minimum 3 required" in reason
        assert "30%" in reason

    def test_continues_at_ratio_threshold(self):
        h = TerminationHandler(
            policy=TerminationPolicy.ADAPTIVE,
            min_clients_threshold=1,
            min_clients_ratio=0.3,
        )
        stop, _ = h.should_terminate(
            available_clients=3, total_clients=10, round_num=2, removed_count=7
        )
        assert stop is False

    def test_min_adaptive_floor_is_one(self):
        # 0.3 * 2 = 0 -> max(1, 0) = 1, so 0 available terminates
        h = TerminationHandler(
            policy=TerminationPolicy.ADAPTIVE,
            min_clients_threshold=1,
            min_clients_ratio=0.3,
            logger=Mock(),
        )
        stop, reason = h.should_terminate(
            available_clients=0, total_clients=2, round_num=1, removed_count=2
        )
        assert stop is True
        assert "minimum 1 required" in reason

    def test_custom_ratio_changes_threshold(self):
        # 50% of 10 = 5, so 4 available -> terminate
        h = TerminationHandler(
            policy=TerminationPolicy.ADAPTIVE,
            min_clients_threshold=1,
            min_clients_ratio=0.5,
            logger=Mock(),
        )
        stop, reason = h.should_terminate(
            available_clients=4, total_clients=10, round_num=1, removed_count=6
        )
        assert stop is True
        assert "50%" in reason


class TestTerminationSummary:
    def test_summary_before_termination(self):
        h = TerminationHandler(policy=TerminationPolicy.GRACEFUL, min_clients_threshold=5)
        summary = h.get_termination_summary()
        assert summary == {
            "terminated_early": False,
            "termination_round": None,
            "termination_reason": "",
            "termination_policy": "graceful",
        }

    def test_summary_after_strict_termination(self):
        h = TerminationHandler(
            policy=TerminationPolicy.STRICT, min_clients_threshold=5, logger=Mock()
        )
        h.should_terminate(
            available_clients=2, total_clients=10, round_num=4, removed_count=8
        )
        summary = h.get_termination_summary()
        assert summary["terminated_early"] is True
        assert summary["termination_round"] == 4
        assert "STRICT policy" in summary["termination_reason"]
        assert summary["termination_policy"] == "strict"

    def test_summary_serializable_to_json(self):
        import json

        h = TerminationHandler(policy=TerminationPolicy.ADAPTIVE, min_clients_threshold=1)
        # Must round-trip through json without TypeError
        json.dumps(h.get_termination_summary())


class TestMarkTerminationLogging:
    def test_mark_termination_logs_at_error_level(self):
        mock_logger = Mock()
        h = TerminationHandler(
            policy=TerminationPolicy.STRICT, min_clients_threshold=5, logger=mock_logger
        )
        h._mark_termination(round_num=3, reason="test reason")
        mock_logger.error.assert_called_once()
        msg = mock_logger.error.call_args.args[0]
        assert "EXPERIMENT TERMINATION" in msg
        assert "test reason" in msg
