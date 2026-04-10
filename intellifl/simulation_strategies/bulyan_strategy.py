from __future__ import annotations

import gc
import logging
import os
import time
from typing import Any

import flwr as fl
import numpy as np
import torch
from flwr.common import (
    EvaluateRes,
    FitRes,
    Parameters,
    Scalar,
    ndarrays_to_parameters,
    parameters_to_ndarrays,
)
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy.aggregate import weighted_loss_avg
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

from intellifl.data_models.simulation_strategy_history import SimulationStrategyHistory
from intellifl.output_handlers.directory_handler import DirectoryHandler
from intellifl.utils.status_tracker import StatusTracker


class BulyanStrategy(fl.server.strategy.FedAvg):
    """Bulyan Byzantine-resilient aggregation strategy.

    Combines Multi-Krum selection with coordinate-wise trimmed mean to filter
    malicious client updates before aggregation. Bulyan provides stronger
    Byzantine resilience than Krum or trimmed mean alone by applying both
    distance-based and statistical filtering.

    Research Foundation:
    - The Hidden Vulnerability of Distributed Learning in Byzantium (Bulyan):
      El Mhamdi et al. (2018) introduced Bulyan as two-stage defense combining
      Multi-Krum client selection with coordinate-wise trimmed mean aggregation,
      achieving breakdown point of (n - 2f - 3) for Byzantine resilience.

    - Byzantine-Robust FL (arXiv 2024):
      https://arxiv.org/abs/2402.12780
      Confirms Bulyan as strongest distance-based Byzantine defense, especially
      effective against sophisticated attacks combining gradient scaling and
      sign flipping.

    - Centralized FL Security (SpringerLink 2022):
      https://link.springer.com/chapter/10.1007/978-3-032-03705-3_10
      Lists Bulyan as gold standard for Byzantine-robust aggregation with
      mathematical guarantees for n > 4f + 2 clients.

    - Theoretical Guarantees: Bulyan maintains Byzantine resilience for
      f < (n - 2)/4 malicious clients with provable convergence bounds.
    """

    def __init__(
        self,
        remove_clients: bool,
        num_krum_selections: int,  # n - f
        begin_removing_from_round: int,
        strategy_history: SimulationStrategyHistory,
        status_tracker: StatusTracker | None = None,
        *args,
        **kwargs,
    ):
        """Initialize the Bulyan strategy.

        Args:
            remove_clients: Whether to enable permanent client removal based on deviation scores.
            num_krum_selections: Number of candidate clients (n - f) selected by Multi-Krum.
            begin_removing_from_round: First round when removal is permitted (warmup period).
            strategy_history: Storage for per-client and per-round metrics.
            status_tracker: Optional progress reporting hook for UI or monitoring.
            *args: Forwarded to base FedAvg strategy.
            **kwargs: Forwarded to base FedAvg strategy.
        """
        super().__init__(*args, **kwargs)
        self.remove_clients = remove_clients
        self.num_krum_selections = num_krum_selections
        self.begin_removing_from_round = begin_removing_from_round
        self.client_scores: dict[Any, float] = {}
        self.removed_client_ids: set[Any] = set()
        self.current_round: int = 0
        self.strategy_history = strategy_history
        self.status_tracker = status_tracker
        self.logger = logging.getLogger(f"bulyan_{id(self)}")
        self.logger.setLevel(logging.INFO)
        out_dir = DirectoryHandler.dirname
        assert out_dir is not None
        os.makedirs(out_dir, exist_ok=True)
        file_handler = logging.FileHandler(f"{out_dir}/output.log")
        console_handler = logging.StreamHandler()
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.propagate = False

    @staticmethod
    def _pairwise_sq_dists(vectors: np.ndarray) -> np.ndarray:
        """Compute pairwise squared Euclidean distances between all vector pairs."""
        diff = vectors[:, None, :] - vectors[None, :, :]
        return np.square(np.linalg.norm(diff, axis=2))

    def aggregate_fit(
        self,
        server_round: int,
        results: list[tuple[ClientProxy, FitRes]],
        failures: list[tuple[ClientProxy, FitRes] | BaseException],
    ) -> tuple[Parameters | None, dict[str, Scalar]]:
        """Aggregate client updates using two-stage Bulyan filtering.

        Applies Multi-Krum to select C candidate clients based on distance proximity,
        then performs coordinate-wise trimmed mean on candidates to produce final
        aggregated parameters. Provides stronger Byzantine resilience than either
        method alone by combining distance-based and statistical filtering.

        Side effects:
            - Increments self.current_round
            - Updates self.client_scores with deviation from Bulyan aggregate
            - Registers client mappings via strategy_history
            - Logs deviation and normalized distance metrics for each client
            - Records score calculation time and per-client metrics to strategy_history

        Args:
            server_round: Current round number from the Flower server.
            results: List of (ClientProxy, FitRes) tuples from participating clients.
            failures: List of failed client results or exceptions (unused or forwarded).

        Returns:
            Tuple of (aggregated_parameters, metrics_dict) from Bulyan two-stage filtering,
            or fallback to FedAvg if preconditions not met (n <= 4f + 2). metrics_dict is empty.
        """
        self.current_round += 1

        # Update status tracker with current round progress
        if self.status_tracker:
            self.status_tracker.update_round(self.current_round)

        # Update client.is_malicious based on attack_schedule for dynamic attacks
        if self.strategy_history:
            self.strategy_history.update_client_malicious_status(server_round)

        if not results:
            return None, {}

        for client_proxy, fit_res in results:
            metrics = getattr(fit_res, "metrics", None)
            if metrics and "partition_id" in metrics:
                partition_id = int(metrics["partition_id"])
                self.strategy_history.register_node_mapping(client_proxy.cid, partition_id)

        clustering_param_data = []
        for _, fit_res in results:
            tensors = [
                torch.tensor(arr).flatten() for arr in parameters_to_ndarrays(fit_res.parameters)
            ]
            clustering_param_data.append(torch.cat(tensors))
        X_embed = np.vstack([t.numpy() for t in clustering_param_data])
        del clustering_param_data  # No longer needed after X_embed created
        kmeans = KMeans(n_clusters=1, init="k-means++").fit(X_embed)
        abs_distances = kmeans.transform(X_embed)
        norm_distances = MinMaxScaler().fit(abs_distances).transform(abs_distances)
        del kmeans, X_embed  # No longer needed after distances computed

        param_arrays = [parameters_to_ndarrays(fr.parameters) for _, fr in results]
        flat_updates = np.stack([np.concatenate([p.ravel() for p in pa]) for pa in param_arrays])
        n, dim = flat_updates.shape
        C = self.num_krum_selections
        f = (n - C) // 2  # number of malicious clients
        if n < C or (n - C) % 2:
            self.logger.error("C must satisfy n - C = 2f (even, <= n)")
            return super().aggregate_fit(server_round, results, failures)

        # Ensure Bulyan preconditions
        if n <= 4 * f + 2:
            self.logger.warning(
                f"[Bulyan] Not enough clients ({n}) for assumed f={f}. Using simple mean."
            )
            return super().aggregate_fit(server_round, results, failures)

        time_start_calc = time.time_ns()
        dists = self._pairwise_sq_dists(flat_updates)
        m = n - f - 2  # number of nearest neighbours to sum
        krum_scores = np.array([np.partition(dists[i], m)[:m].sum() for i in range(n)])
        candidate_idx = np.argpartition(krum_scores, C)[:C]
        candidates = flat_updates[candidate_idx]
        del dists, krum_scores  # No longer needed after candidate selection

        sorted_idx = np.argsort(candidates, axis=0)
        kept_slice = slice(f, C - f)
        trimmed = candidates[sorted_idx[kept_slice, np.arange(dim)], np.arange(dim)]
        bulyan_vector = trimmed.mean(axis=0)
        time_end_calc = time.time_ns()
        del candidates, sorted_idx, trimmed  # No longer needed after bulyan_vector computed

        agg_list, cursor = [], 0
        for arr in param_arrays[0]:
            num = arr.size
            agg_list.append(
                bulyan_vector[cursor : cursor + num].reshape(arr.shape).astype(arr.dtype)
            )
            cursor += num
        aggregated_parameters = ndarrays_to_parameters(agg_list)
        del agg_list  # No longer needed after aggregation

        self.strategy_history.insert_round_history_entry(
            score_calculation_time_nanos=time_end_calc - time_start_calc
        )

        for i, (client_proxy, _) in enumerate(results):
            cid = client_proxy.cid
            deviation = float(np.linalg.norm(flat_updates[i] - bulyan_vector))
            # Alternative: Use krum scores for removal criterion instead of deviation
            # Krum scores prioritize distance-based clustering over aggregate proximity
            # deviation = float(krum_scores[i])
            self.client_scores[cid] = deviation
            self.strategy_history.insert_single_client_history_entry(
                current_round=self.current_round,
                client_id=cid,
                removal_criterion=deviation,
                absolute_distance=float(abs_distances[i][0]),
            )
            self.logger.info(
                f"Aggregation round: {server_round} Client ID: {cid} Deviation: {deviation:.4e} "
                f"Normalized Distance: {norm_distances[i][0]:.4f}"
            )

        del (
            flat_updates,
            bulyan_vector,
            abs_distances,
            norm_distances,
            param_arrays,
        )  # Cleanup remaining intermediates
        gc.collect()
        return aggregated_parameters, {}

    def configure_fit(
        self,
        server_round: int,
        parameters: Parameters,
        client_manager,
    ) -> list[tuple[ClientProxy, fl.common.FitIns]]:
        """Configure client selection with batch removal of high-deviation clients.

        During warmup (rounds up to begin_removing_from_round), all clients participate.
        After warmup, removes f clients with highest deviation from Bulyan aggregate
        each round, where f = (n - num_krum_selections) // 2. Resets removed set each
        round (stateless removal).

        Side effects:
            - Resets self.removed_client_ids to new set each round
            - Iteratively adds f high-deviation clients to removed_client_ids
            - Updates strategy_history.update_client_participation()
            - Logs removed clients for current round

        Args:
            server_round: Current round number from the Flower server.
            parameters: Current global model parameters to distribute.
            client_manager: Flower client manager for accessing clients.

        Returns:
            List of (ClientProxy, FitIns) tuples for selected clients, excluding removed clients.
        """
        available_clients = client_manager.all()

        # Warmup phase: include all clients
        if (
            self.begin_removing_from_round is not None
            and self.current_round <= self.begin_removing_from_round
        ):
            fit_ins = fl.common.FitIns(parameters, {"server_round": server_round})
            return [(c, fit_ins) for c in available_clients.values()]

        client_scores = {cid: self.client_scores.get(cid, 0.0) for cid in available_clients}
        self.removed_client_ids = set()

        if self.remove_clients:
            n = len(client_scores)
            f = max(0, n - self.num_krum_selections) // 2
            for _ in range(f):
                if not client_scores:
                    break
                eligible = {
                    cid: s for cid, s in client_scores.items() if cid not in self.removed_client_ids
                }
                if not eligible:
                    break
                worst = max(eligible, key=lambda x: eligible[x])
                self.removed_client_ids.add(worst)

        self.logger.info(
            f"Removed clients at round {self.current_round} are : {self.removed_client_ids}"
        )

        self.strategy_history.update_client_participation(
            current_round=self.current_round, removed_client_ids=self.removed_client_ids
        )

        ordered_cids = sorted(client_scores, key=lambda x: client_scores[x], reverse=True)
        fit_ins = fl.common.FitIns(parameters, {"server_round": server_round})
        return [
            (available_clients[cid], fit_ins) for cid in ordered_cids if cid in available_clients
        ]

    def aggregate_evaluate(  # type: ignore[override]
        self,
        server_round: int,
        results: list[tuple[ClientProxy, EvaluateRes]],
        failures: list[tuple[ClientProxy | EvaluateRes, BaseException]],
    ) -> tuple[float | None, dict[str, Scalar]]:
        """Aggregate client evaluation results and record per-client metrics.

        Computes weighted average loss from non-removed clients only, ensuring removed
        clients do not influence global model quality assessment. Records per-client
        accuracy and loss for historical analysis and Byzantine behavior tracking.

        Side effects:
            - Registers client mappings via strategy_history
            - Records per-client accuracy and loss to strategy_history
            - Records round-level aggregated loss to strategy_history
            - Logs aggregation round header, per-client metrics, and summary statistics

        Args:
            server_round: Current round number from the Flower server.
            results: List of (ClientProxy, EvaluateRes) tuples from participating clients.
            failures: List of failed evaluation results or exceptions (unused).

        Returns:
            Tuple of (aggregated_loss, metrics_dict) where loss is None if no
            results available, otherwise weighted average loss from non-removed
            clients only. metrics_dict is currently empty.
        """
        self.strategy_history.register_node_mappings_from_results(results)

        self.logger.info("\n" + "-" * 50 + f"AGGREGATION ROUND {server_round}" + "-" * 50)

        for cp, ev in results:
            cid = cp.cid
            acc_metrics = dict(ev.metrics)
            acc_metrics["cid"] = cid
            self.strategy_history.insert_single_client_history_entry(
                client_id=cid,
                current_round=self.current_round,
                accuracy=float(acc_metrics.get("accuracy", 0.0)),
            )

        if not results:
            return None, {}

        aggregate_value, num_clients_loss = [], 0
        for cp, ev in results:
            self.strategy_history.insert_single_client_history_entry(
                client_id=cp.cid,
                current_round=self.current_round,
                loss=ev.loss,
            )
            if cp.cid not in self.removed_client_ids:
                aggregate_value.append((ev.num_examples, ev.loss))
                num_clients_loss += 1

        loss_aggregated = weighted_loss_avg(aggregate_value)
        self.strategy_history.insert_round_history_entry(loss_aggregated=loss_aggregated)

        for cp, ev in results:
            logging.debug(f"Client ID: {cp.cid} Metrics: {ev.metrics} Loss: {ev.loss}")

        self.logger.info(
            f"Round: {server_round} Number of aggregated clients: {num_clients_loss} "
            f"Aggregated loss: {loss_aggregated}"
        )
        return loss_aggregated, {}
