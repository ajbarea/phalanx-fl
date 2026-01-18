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

    Note: These tests require full simulation setup and are more expensive.
    Run with: pytest -m integration tests/integration/test_client_removal_termination.py
    """

    @pytest.mark.skip(reason="Requires full simulation setup - manual test recommended")
    def test_pid_removal_with_graceful_policy(self):
        """Test PID removal strategy with GRACEFUL policy in all-malicious scenario."""
        # TODO: Implement full integration test
        # 1. Create config with all clients malicious
        # 2. Run simulation with PID removal + GRACEFUL policy
        # 3. Verify simulation continues until 0 clients
        # 4. Check final metrics dictionary for termination info
        pass

    @pytest.mark.skip(reason="Requires full simulation setup - manual test recommended")
    def test_trust_removal_with_strict_policy(self):
        """Test Trust removal strategy with STRICT policy early termination."""
        # TODO: Implement full integration test
        # 1. Create config with aggressive trust threshold
        # 2. Run simulation with Trust removal + STRICT policy
        # 3. Verify simulation terminates when below min_fit_clients
        # 4. Check logs for ERROR-level termination messages
        pass

    @pytest.mark.skip(reason="Requires full simulation setup - manual test recommended")
    def test_rfa_removal_with_adaptive_policy(self):
        """Test RFA removal strategy with ADAPTIVE policy threshold behavior."""
        # TODO: Implement full integration test
        # 1. Create config with moderate malicious count
        # 2. Run simulation with RFA removal + ADAPTIVE policy (30% threshold)
        # 3. Verify simulation terminates around 30% client count
        # 4. Validate metrics show correct termination reason
        pass


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
