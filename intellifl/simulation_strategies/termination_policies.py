"""
Termination policies for federated learning client removal scenarios.

This module provides configurable policies for handling insufficient client
availability in Byzantine-robust federated learning. Research shows that
client removal and sampling rates significantly impact model performance
and robustness.

References:
- Byzantine-Robust FL with Client Subsampling (arXiv 2024):
  https://arxiv.org/abs/2402.12780
  Key finding: Client subsampling increases effective fraction of Byzantine clients
- Centralized FL Security Framework (SpringerLink 2022):
  https://link.springer.com/chapter/10.1007/978-3-032-03705-3_10
  Covers detection methods and robust aggregation standards
- FL Issues in Practice (Nature 2024):
  https://www.nature.com/articles/s41598-024-81732-0
  Discusses client dropout handling and sampling effects on accuracy
"""

from __future__ import annotations

import logging
from enum import StrEnum


class TerminationPolicy(StrEnum):
    """Policy for handling insufficient client availability.

    Different policies support different experimental paradigms:
    - Research exploration: GRACEFUL allows observation of degradation
    - Production requirements: STRICT ensures minimum federation size
    - Adaptive experiments: ADAPTIVE balances both approaches
    """

    GRACEFUL = "graceful"
    """
    Continue with available clients, warn researcher. Terminates only at 0 clients.

    Best for: Observing system degradation behavior and Byzantine robustness studies.
    Use when: Exploring how federation quality degrades with client removal.
    """

    STRICT = "strict"
    """
    Terminate immediately if available clients < min_fit_clients.

    Best for: Production-quality experiments requiring minimum federation size.
    Use when: Results are only meaningful with sufficient client participation.
    """

    ADAPTIVE = "adaptive"
    """
    Dynamically adjust minimum based on remaining clients (default 30% threshold).

    Best for: Balancing exploration with meaningful federation size.
    Use when: Need early warning but want to observe degradation patterns.
    Note: Research shows sampling rates below 50% cause accuracy degradation.
    """


class TerminationHandler:
    """
    Handles experiment termination logic for client removal scenarios.

    Example:
        >>> handler = TerminationHandler(
        ...     policy=TerminationPolicy.GRACEFUL,
        ...     min_clients_threshold=5,
        ...     logger=my_logger
        ... )
        >>> should_stop, reason = handler.should_terminate(
        ...     available_clients=3,
        ...     total_clients=10,
        ...     round_num=5,
        ...     removed_count=7
        ... )
        >>> if should_stop:
        ...     print(f"Terminating: {reason}")
    """

    def __init__(
        self,
        policy: TerminationPolicy | str,
        min_clients_threshold: int,
        min_clients_ratio: float = 0.3,  # 30% of original
        logger: logging.Logger | None = None,
    ):
        """
        Initialize termination handler.

        Args:
            policy: Termination policy to use (GRACEFUL, STRICT, or ADAPTIVE)
            min_clients_threshold: Minimum number of clients required (for STRICT policy)
            min_clients_ratio: Minimum ratio of clients required (for ADAPTIVE policy)
                             Default 0.3 (30%) provides early warning while allowing
                             degradation study. Research shows 50%+ maintains accuracy.
            logger: Optional logger for recording termination decisions
        """
        self.policy = TerminationPolicy(policy) if isinstance(policy, str) else policy
        self.min_threshold = min_clients_threshold
        self.min_ratio = min_clients_ratio
        self.logger = logger or logging.getLogger(__name__)
        self.termination_triggered = False
        self.termination_round: int | None = None
        self.termination_reason = ""

    def should_terminate(
        self,
        available_clients: int,
        total_clients: int,
        round_num: int,
        removed_count: int,
    ) -> tuple[bool, str]:
        """
        Determine if experiment should terminate based on client availability.

        Args:
            available_clients: Number of clients currently available for aggregation
            total_clients: Total number of clients at experiment start
            round_num: Current round number
            removed_count: Total number of clients removed so far

        Returns:
            (should_stop, reason): Boolean indicating termination and reason string
        """
        if self.policy == TerminationPolicy.STRICT:
            if available_clients < self.min_threshold:
                reason = (
                    f"STRICT policy: {available_clients} clients available, "
                    f"minimum {self.min_threshold} required"
                )
                self._mark_termination(round_num, reason)
                return True, reason

        elif self.policy == TerminationPolicy.GRACEFUL:
            if available_clients == 0:
                reason = "GRACEFUL policy: No clients available (all removed)"
                self._mark_termination(round_num, reason)
                return True, reason
            # Otherwise continue with warning
            if available_clients < self.min_threshold:
                self.logger.warning(
                    f"Round {round_num}: Below minimum threshold "
                    f"({available_clients} < {self.min_threshold}), "
                    f"continuing anyway (GRACEFUL policy)"
                )

        elif self.policy == TerminationPolicy.ADAPTIVE:
            # Adaptive policy: terminate if below percentage threshold
            # Default 30% balances warning with exploration
            # Research shows 50%+ sampling maintains accuracy
            min_adaptive = max(1, int(total_clients * self.min_ratio))
            if available_clients < min_adaptive:
                reason = (
                    f"ADAPTIVE policy: {available_clients} clients available, "
                    f"minimum {min_adaptive} required "
                    f"({self.min_ratio * 100:.0f}% of {total_clients})"
                )
                self._mark_termination(round_num, reason)
                return True, reason

        return False, ""

    def _mark_termination(self, round_num: int, reason: str):
        """
        Record termination event for reporting.

        Args:
            round_num: Round number where termination occurred
            reason: Human-readable reason for termination
        """
        self.termination_triggered = True
        self.termination_round = round_num
        self.termination_reason = reason
        self.logger.error(f"EXPERIMENT TERMINATION: {reason}")

    def get_termination_summary(self) -> dict:
        """
        Get termination details for reporting and analysis.

        Returns:
            Dictionary with termination status, round, reason, and policy used.
            Suitable for JSON serialization and CSV output.
        """
        return {
            "terminated_early": self.termination_triggered,
            "termination_round": self.termination_round,
            "termination_reason": self.termination_reason,
            "termination_policy": self.policy.value,
        }
