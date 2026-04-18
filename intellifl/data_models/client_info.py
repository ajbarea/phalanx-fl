from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class ClientInfo:
    client_id: int
    num_of_rounds: int
    is_malicious: bool | None = None
    rounds: list[int] = field(default_factory=list)

    removal_criterion_history: list[float | None] = field(default_factory=list)
    absolute_distance_history: list[float | None] = field(default_factory=list)
    loss_history: list[float | None] = field(default_factory=list)
    accuracy_history: list[float | None] = field(default_factory=list)
    aggregation_participation_history: list[int | None] = field(default_factory=list)

    plottable_metrics: ClassVar[list[str]] = [
        "removal_criterion_history",
        "absolute_distance_history",
        "loss_history",
        "accuracy_history",
    ]

    savable_metrics: ClassVar[list[str]] = [
        "removal_criterion_history",
        "absolute_distance_history",
        "loss_history",
        "accuracy_history",
        "aggregation_participation_history",
    ]

    def __post_init__(self) -> None:
        def _init_list(value: Any = None) -> list[Any]:
            return [value] * self.num_of_rounds

        self.removal_criterion_history = _init_list()
        self.absolute_distance_history = _init_list()
        self.loss_history = _init_list()
        self.accuracy_history = _init_list()
        self.aggregation_participation_history = _init_list(value=0)

        self.rounds = []

        for round_num in range(self.num_of_rounds):
            self.rounds.append(round_num + 1)

    def add_history_entry(
        self,
        current_round: int,
        removal_criterion: float | None = None,
        absolute_distance: float | None = None,
        loss: float | None = None,
        accuracy: float | None = None,
        aggregation_participation: int | None = None,
    ) -> None:
        """
        Add client metrics history entry for a new round.

        :param current_round: specifies the round number to put all data into correct index at list
        :param accuracy: accuracy at this round
        :param loss: loss at this round
        :param removal_criterion: calculated score based on which the removal was or was not performed
        :param absolute_distance: to the centroid of all models
        :param aggregation_participation: 1 if client was aggregated, 0 if was not
        """

        if removal_criterion is not None:
            self.removal_criterion_history[current_round - 1] = removal_criterion
        if absolute_distance is not None:
            self.absolute_distance_history[current_round - 1] = absolute_distance
        if loss is not None:
            self.loss_history[current_round - 1] = loss
        if accuracy is not None:
            self.accuracy_history[current_round - 1] = accuracy
        if aggregation_participation is not None:
            self.aggregation_participation_history[current_round - 1] = aggregation_participation

    def get_metric_by_name(self, metric: str) -> list:
        """Get single plottable or savable metric values by name"""

        return getattr(self, metric)
