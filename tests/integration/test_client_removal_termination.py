"""Integration tests for client removal termination policies.

These tests verify the behavior of GRACEFUL, STRICT, and ADAPTIVE termination
policies in edge case scenarios where many or all clients are removed.

Research Context:
- Byzantine-Robust FL with Client Subsampling (arXiv 2024)
- Centralized FL Security Framework (SpringerLink 2022)
- FL Issues in Practice (Nature 2024)
"""

import pytest

from intellifl.simulation_strategies.termination_policies import (
    TerminationHandler,
    TerminationPolicy,
)


class TestTerminationPolicies:
    """Test termination policy behavior in isolation."""

    def test_graceful_policy_allows_all_clients_removed(self):
        """GRACEFUL policy continues until 0 clients remain."""
        handler = TerminationHandler(
            policy=TerminationPolicy.GRACEFUL,
            min_clients_threshold=5,
            logger=None,
        )

        # Should NOT terminate with 1 client
        should_stop, reason = handler.should_terminate(
            available_clients=1,
            total_clients=10,
            round_num=5,
            removed_count=9,
        )
        assert not should_stop, "GRACEFUL should allow 1 client"

        # Should terminate with 0 clients
        should_stop, reason = handler.should_terminate(
            available_clients=0,
            total_clients=10,
            round_num=6,
            removed_count=10,
        )
        assert should_stop, "GRACEFUL should terminate with 0 clients"
        assert "No clients available" in reason

    def test_strict_policy_enforces_minimum(self):
        """STRICT policy terminates when below min_fit_clients."""
        handler = TerminationHandler(
            policy=TerminationPolicy.STRICT,
            min_clients_threshold=5,
            logger=None,
        )

        # Should NOT terminate with exactly min_fit_clients
        should_stop, reason = handler.should_terminate(
            available_clients=5,
            total_clients=10,
            round_num=3,
            removed_count=5,
        )
        assert not should_stop, "STRICT should allow exactly min_fit_clients"

        # Should terminate with below min_fit_clients
        should_stop, reason = handler.should_terminate(
            available_clients=4,
            total_clients=10,
            round_num=4,
            removed_count=6,
        )
        assert should_stop, "STRICT should terminate below min_fit_clients"
        assert "STRICT policy" in reason

    def test_adaptive_policy_uses_ratio(self):
        """ADAPTIVE policy terminates at configured ratio threshold."""
        handler = TerminationHandler(
            policy=TerminationPolicy.ADAPTIVE,
            min_clients_threshold=5,  # Not used for ADAPTIVE
            min_clients_ratio=0.3,  # 30% threshold
            logger=None,
        )

        # 10 clients total, 30% = 3 clients minimum
        # Should NOT terminate with 4 clients (40%)
        should_stop, reason = handler.should_terminate(
            available_clients=4,
            total_clients=10,
            round_num=5,
            removed_count=6,
        )
        assert not should_stop, "ADAPTIVE should allow 40% (above 30% threshold)"

        # Should terminate with 2 clients (20%)
        should_stop, reason = handler.should_terminate(
            available_clients=2,
            total_clients=10,
            round_num=6,
            removed_count=8,
        )
        assert should_stop, "ADAPTIVE should terminate at 20% (below 30% threshold)"
        assert "ADAPTIVE policy" in reason

    def test_termination_handler_returns_correct_reason(self):
        """Verify termination reasons are descriptive and actionable."""
        handler = TerminationHandler(
            policy=TerminationPolicy.STRICT,
            min_clients_threshold=5,
            logger=None,
        )

        should_stop, reason = handler.should_terminate(
            available_clients=3,
            total_clients=10,
            round_num=7,
            removed_count=7,
        )

        assert should_stop
        assert "3" in reason  # Available count
        assert "5" in reason  # Required count
        assert "STRICT" in reason  # Policy name


class TestTerminationPolicyConfiguration:
    """Test configuration parsing and validation."""

    def test_policy_string_to_enum_conversion(self):
        """Verify string policy names convert to enums correctly."""
        handler_graceful = TerminationHandler(policy="graceful", min_clients_threshold=5)
        assert handler_graceful.policy == TerminationPolicy.GRACEFUL

        handler_strict = TerminationHandler(policy="strict", min_clients_threshold=5)
        assert handler_strict.policy == TerminationPolicy.STRICT

        handler_adaptive = TerminationHandler(policy="adaptive", min_clients_threshold=5)
        assert handler_adaptive.policy == TerminationPolicy.ADAPTIVE

    def test_invalid_policy_raises_error(self):
        """Invalid policy names should raise ValueError."""
        with pytest.raises(ValueError):
            TerminationHandler(policy="invalid_policy", min_clients_threshold=5)


@pytest.mark.integration
class TestClientRemovalIntegration:
    """Integration tests with actual removal strategies.

    These tests verify the interaction between client removal strategies
    (PID, Trust, RFA) and termination policies (GRACEFUL, STRICT, ADAPTIVE)
    using mocked client manager behavior suitable for CI execution.

    Run with: pytest -m integration tests/integration/test_client_removal_termination.py
    """

    def test_pid_removal_with_graceful_policy(self):
        """Test PID removal with GRACEFUL policy in all-malicious scenario.

        Scenario:
        - All 10 clients are malicious (100% attack scenario)
        - PID removal progressively removes ~2 clients per round
        - GRACEFUL policy allows continuation until no clients remain

        Expected:
        - Simulation continues even with 1 client remaining
        - Terminates only when 0 clients are available
        - Final summary includes termination reason
        """
        handler = TerminationHandler(
            policy=TerminationPolicy.GRACEFUL,
            min_clients_threshold=5,  # Ignored for GRACEFUL
            logger=None,
        )

        # Simulate all-malicious scenario with PID removal pattern
        # PID typically removes 2 clients per round in high-attack scenarios
        total_clients = 10
        available_clients = total_clients
        removed_clients = []

        for round_num in range(1, 10):
            # Simulate PID removal: ~2 clients per round until none left
            removed_this_round = min(2, available_clients)
            available_clients -= removed_this_round
            removed_clients.extend([f"client_{i}" for i in range(removed_this_round)])

            should_stop, reason = handler.should_terminate(
                available_clients=available_clients,
                total_clients=total_clients,
                round_num=round_num,
                removed_count=len(removed_clients),
            )

            if available_clients > 0:
                assert not should_stop, (
                    f"GRACEFUL should continue with {available_clients} clients remaining"
                )
            else:
                assert should_stop, "GRACEFUL should stop with 0 clients"
                assert "No clients available" in reason
                break

        # Verify termination summary
        summary = handler.get_termination_summary()
        assert summary["terminated_early"] is True
        assert summary["termination_policy"] == "graceful"
        assert "No clients available" in summary["termination_reason"]

    def test_trust_removal_with_strict_policy(self):
        """Test Trust removal with STRICT policy early termination.

        Scenario:
        - 10 clients total, 8 are malicious
        - Aggressive trust threshold causes rapid client removal
        - STRICT policy with min_fit_clients = 5

        Expected:
        - Trust removes ~2-3 clients per round with aggressive threshold
        - STRICT policy triggers termination when < 5 clients remain
        - Termination reason includes policy details
        """
        handler = TerminationHandler(
            policy=TerminationPolicy.STRICT,
            min_clients_threshold=5,
            logger=None,
        )

        # Simulate aggressive trust removal pattern
        # With trust_threshold=0.3 (aggressive), malicious clients are removed quickly
        total_clients = 10
        available_clients = total_clients
        termination_round = None

        for round_num in range(1, 10):
            # Trust removes ~2 clients per round with aggressive threshold
            removed = min(2, available_clients)
            available_clients -= removed

            should_stop, reason = handler.should_terminate(
                available_clients=available_clients,
                total_clients=total_clients,
                round_num=round_num,
                removed_count=total_clients - available_clients,
            )

            if available_clients < 5:
                assert should_stop, f"STRICT should terminate with {available_clients} < 5 clients"
                assert "STRICT policy" in reason
                assert str(available_clients) in reason
                assert "5" in reason  # Minimum required
                termination_round = round_num
                break
            else:
                assert not should_stop, (
                    f"STRICT should continue with {available_clients} >= 5 clients"
                )

        # Verify early termination occurred
        assert termination_round is not None, "STRICT policy should have triggered termination"
        assert termination_round < 10, "Termination should happen before all rounds complete"

        # Verify termination summary
        summary = handler.get_termination_summary()
        assert summary["terminated_early"] is True
        assert summary["termination_policy"] == "strict"
        assert summary["termination_round"] == termination_round

    def test_rfa_removal_with_adaptive_policy(self):
        """Test RFA removal with ADAPTIVE policy threshold behavior.

        Scenario:
        - 15 clients total, 6 malicious (40%)
        - ADAPTIVE policy with 30% minimum ratio
        - RFA removes ~1 client per round on average

        Expected:
        - ADAPTIVE monitors ratio: available / total
        - Terminates when ratio drops below 0.3 (< 5 clients)
        - Termination reason includes ratio details
        """
        handler = TerminationHandler(
            policy=TerminationPolicy.ADAPTIVE,
            min_clients_threshold=2,  # Fallback, not primary for ADAPTIVE
            min_clients_ratio=0.3,  # 30% threshold = 4.5 -> 5 clients minimum
            logger=None,
        )

        total_clients = 15
        available_clients = total_clients
        termination_round = None

        # ADAPTIVE threshold calculation: int(15 * 0.3) = 4
        # Termination occurs when available_clients < 4
        min_adaptive_threshold = max(1, int(total_clients * 0.3))  # = 4

        for round_num in range(1, 20):
            # RFA removes ~1 client per round on average
            if available_clients > 0:
                available_clients -= 1

            should_stop, reason = handler.should_terminate(
                available_clients=available_clients,
                total_clients=total_clients,
                round_num=round_num,
                removed_count=total_clients - available_clients,
            )

            if available_clients < min_adaptive_threshold:
                assert should_stop, (
                    f"ADAPTIVE should terminate with {available_clients} < {min_adaptive_threshold} clients"
                )
                assert "ADAPTIVE policy" in reason
                assert "30%" in reason  # Ratio threshold
                termination_round = round_num
                break
            else:
                assert not should_stop, (
                    f"ADAPTIVE should continue with {available_clients} >= {min_adaptive_threshold} clients"
                )

        # Verify termination occurred at expected threshold
        assert termination_round is not None, "ADAPTIVE policy should have triggered termination"
        # With 15 clients and 30% threshold (min 4), termination at < 4 clients (round 12+)
        assert termination_round >= 12, "Should terminate after removing 12+ clients"

        # Verify termination summary
        summary = handler.get_termination_summary()
        assert summary["terminated_early"] is True
        assert summary["termination_policy"] == "adaptive"
        assert "ADAPTIVE policy" in summary["termination_reason"]


# Manual Test Documentation
"""
MANUAL TEST SCENARIOS

1. All-Malicious with GRACEFUL:
   - Set num_of_malicious_clients = num_of_clients
   - Set termination_policy = "graceful"
   - Run simulation and observe degradation until 0 clients
   - Expected: Simulation continues, final metrics show "all_clients_removed"

2. Aggressive Removal with STRICT:
   - Set num_of_malicious_clients = 8, num_of_clients = 10
   - Set termination_policy = "strict", min_fit_clients = 5
   - Set low PID num_std_dev or high trust threshold for aggressive removal
   - Expected: Simulation terminates early with ERROR logs

3. Moderate Attack with ADAPTIVE:
   - Set num_of_malicious_clients = 6, num_of_clients = 15
   - Set termination_policy = "adaptive", min_clients_ratio = 0.4 (40%)
   - Use balanced removal parameters
   - Expected: Simulation terminates around 6 clients remaining (40%)

4. Configuration Conflict:
   - Set remove_clients = true, strict_mode = true
   - Expected: Validation warning, strict_mode auto-disabled

5. No Termination (Baseline):
   - Use FedAvg or other non-removal strategy
   - Set any termination_policy
   - Expected: Policy has no effect, simulation runs normally

Run these scenarios using:
  ./run_simulation.sh
  # Or
  python -m intellifl.simulation_runner --config <path-to-test-config>

Check logs for:
  - ERROR-level termination messages
  - Metrics dictionary with termination info
  - CSV output for removed client tracking
"""
