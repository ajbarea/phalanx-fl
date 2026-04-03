"""Mock Flower FL components for testing without distributed execution.

Provides mock implementations of Flower's client/server interfaces that
simulate federated learning behavior deterministically using seeded RNG.
Used for testing strategy aggregation logic without Ray/gRPC overhead.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from flwr.common import (
    Code,
    Parameters,
    Status,
    ndarrays_to_parameters,
    parameters_to_ndarrays,
)

type NDArray = np.ndarray
type Config = dict[str, Any]
type Metrics = dict[str, Any]
type Scalar = bool | bytes | float | int | str

TENSOR_TYPE_NUMPY = "numpy.ndarray"


class MockParameters:
    """Lightweight Parameters replacement for testing."""

    def __init__(self, tensors: list[bytes], tensor_type: str = TENSOR_TYPE_NUMPY) -> None:
        self.tensors = tensors
        self.tensor_type = tensor_type

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MockParameters):
            return False
        return self.tensors == other.tensors and self.tensor_type == other.tensor_type


class MockFitRes:
    """Training result container matching Flower's FitRes interface."""

    def __init__(
        self,
        parameters: MockParameters,
        num_examples: int,
        metrics: Metrics | None = None,
    ) -> None:
        self.status = Status(code=Code.OK, message="")
        self.parameters = parameters
        self.num_examples = num_examples
        self.metrics = metrics or {}


class MockEvaluateRes:
    """Evaluation result container matching Flower's EvaluateRes interface."""

    def __init__(self, loss: float, num_examples: int, metrics: Metrics | None = None) -> None:
        self.status = Status(code=Code.OK, message="")
        self.loss = loss
        self.num_examples = num_examples
        self.metrics = metrics or {}


class MockClientProxy:
    """Simulates client-server communication for strategy testing."""

    def __init__(self, cid: str, client_fn: Callable[..., Any] | None = None) -> None:
        self.cid = cid
        self.client_fn = client_fn
        self._mock_client = None

        # Seed RNG per-client for deterministic but varied behavior
        try:
            client_num = int(cid)
        except ValueError:
            client_num = hash(cid) % 1000
        self._rng = np.random.default_rng(42 + client_num)
        self._training_rounds = 0

    def fit(self, parameters: Any, _: Config) -> MockFitRes:
        """Simulate one round of local training with noise injection."""
        self._training_rounds += 1

        if isinstance(parameters, MockParameters):
            updated_tensors = []
            for tensor_bytes in parameters.tensors:
                tensor = np.frombuffer(tensor_bytes, dtype=np.float32)
                noise = self._rng.normal(0, 0.01, tensor.shape).astype(np.float32)
                updated_tensor = tensor + noise
                updated_tensors.append(updated_tensor.tobytes())
            updated_params: Any = MockParameters(updated_tensors, parameters.tensor_type)
        else:
            ndarrays = parameters_to_ndarrays(parameters)
            updated_arrays = []
            for arr in ndarrays:
                noise = self._rng.normal(0, 0.01, arr.shape).astype(arr.dtype)
                updated_arrays.append(arr + noise)
            updated_params = ndarrays_to_parameters(updated_arrays)

        mock_loss = self._rng.uniform(0.1, 2.0)
        mock_accuracy = self._rng.uniform(0.5, 0.95)
        num_examples = int(self._rng.integers(50, 200))

        metrics: Metrics = {
            "loss": mock_loss,
            "accuracy": mock_accuracy,
            "round": self._training_rounds,
        }

        return MockFitRes(updated_params, num_examples, metrics)

    def evaluate(self, _parameters: Any, _config: Config) -> MockEvaluateRes:
        """Return randomized evaluation metrics."""
        mock_loss = self._rng.uniform(0.1, 1.5)
        mock_accuracy = self._rng.uniform(0.6, 0.95)
        num_examples = int(self._rng.integers(30, 100))

        metrics: Metrics = {
            "accuracy": mock_accuracy,
            "f1_score": self._rng.uniform(0.5, 0.9),
        }

        return MockEvaluateRes(mock_loss, num_examples, metrics)


class MockServerConfig:
    """Minimal ServerConfig replacement holding round count."""

    def __init__(self, num_rounds: int) -> None:
        self.num_rounds = num_rounds


class MockNumPyClient:
    """NumPy-based client returning random but deterministic updates."""

    def __init__(self, client_id: int = 0) -> None:
        self.client_id = client_id
        self._rng = np.random.default_rng(42 + client_id)

    def get_parameters(self, _: Config) -> list[NDArray]:
        """Return deterministic initial parameters for this client."""
        self._rng = np.random.default_rng(42 + self.client_id)  # Reset for reproducibility
        return [
            self._rng.standard_normal((100, 10)).astype(np.float32),
            self._rng.standard_normal(10).astype(np.float32),
        ]

    def fit(self, parameters: list[NDArray], _: Config) -> tuple[list[NDArray], int, Metrics]:
        """Add small noise to parameters simulating one training step."""
        updated_params = []
        for param in parameters:
            noise = self._rng.normal(0, 0.01, param.shape).astype(param.dtype)
            updated_params.append(param + noise)

        num_examples = int(self._rng.integers(50, 200))
        metrics: Metrics = {
            "loss": self._rng.uniform(0.1, 2.0),
            "accuracy": self._rng.uniform(0.5, 0.95),
        }

        return updated_params, num_examples, metrics

    def evaluate(self, _parameters: list[NDArray], _config: Config) -> tuple[float, int, Metrics]:
        """Return randomized but plausible evaluation metrics."""
        loss = self._rng.uniform(0.1, 1.5)
        num_examples = int(self._rng.integers(30, 100))
        metrics: Metrics = {
            "accuracy": self._rng.uniform(0.6, 0.95),
            "f1_score": self._rng.uniform(0.5, 0.9),
        }

        return loss, num_examples, metrics


class MockClient:
    """Wrapper delegating to MockNumPyClient with serialization."""

    def __init__(self, numpy_client: MockNumPyClient) -> None:
        self.numpy_client = numpy_client

    def fit(self, parameters: MockParameters, config: Config) -> MockFitRes:
        """Deserialize, delegate to NumPyClient, reserialize."""
        np_params = [np.frombuffer(t, dtype=np.float32) for t in parameters.tensors]

        updated_params, num_examples, metrics = self.numpy_client.fit(np_params, config)

        updated_tensors = [p.tobytes() for p in updated_params]
        updated_parameters = MockParameters(updated_tensors, parameters.tensor_type)

        return MockFitRes(updated_parameters, num_examples, metrics)

    def evaluate(self, parameters: MockParameters, config: Config) -> MockEvaluateRes:
        """Deserialize, delegate to NumPyClient, return result."""
        np_params = [np.frombuffer(t, dtype=np.float32) for t in parameters.tensors]

        loss, num_examples, metrics = self.numpy_client.evaluate(np_params, config)

        return MockEvaluateRes(loss, num_examples, metrics)


def mock_start_simulation(
    client_fn: Callable[[str], MockClient],
    num_clients: int,
    config: MockServerConfig,
    strategy: Any,
    initial_parameters: MockParameters | Parameters | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Execute FL simulation with real strategy but mock clients.

    Runs the full FL loop calling strategy.aggregate_fit/evaluate,
    enabling testing of aggregation logic without distributed infra.

    Args:
        client_fn: Factory function creating clients by cid.
        num_clients: Number of simulated clients.
        config: Server config with round count.
        strategy: Aggregation strategy to test.
        initial_parameters: Starting model parameters.
        **_kwargs: Ignored (compatibility with real start_simulation).

    Returns:
        Dict with history of losses and metrics per round.
    """
    simulation_results: dict[str, Any] = {
        "history": {
            "losses_distributed": [],
            "losses_centralized": [],
            "metrics_distributed": {},
            "metrics_centralized": {},
        },
        "num_rounds": config.num_rounds,
        "num_clients": num_clients,
    }

    client_proxies = []
    for cid in range(num_clients):
        proxy = MockClientProxy(str(cid), client_fn)
        client_proxies.append(proxy)

    if initial_parameters is None:
        rng = np.random.default_rng(42)
        initial_parameters = ndarrays_to_parameters(
            [
                rng.standard_normal((100, 10)).astype(np.float32),
                rng.standard_normal(10).astype(np.float32),
            ]
        )

    assert initial_parameters is not None
    current_params = initial_parameters

    for round_num in range(1, config.num_rounds + 1):
        round_results, new_params = _simulate_round(
            client_proxies, strategy, round_num, num_clients, current_params
        )

        if new_params is not None:
            current_params = new_params

        avg_loss: float = round_results["avg_loss"]
        losses_list: list[float] = simulation_results["history"]["losses_distributed"]
        losses_list.append(avg_loss)

        metrics_dict: dict[str, Any] = round_results["metrics"]
        for metric_name, metric_value in metrics_dict.items():
            distributed_metrics: dict[str, list[Any]] = simulation_results["history"][
                "metrics_distributed"
            ]
            if metric_name not in distributed_metrics:
                distributed_metrics[metric_name] = []
            distributed_metrics[metric_name].append(metric_value)

    return simulation_results


def _simulate_round(
    client_proxies: list[MockClientProxy],
    strategy: Any,
    round_num: int,
    num_clients: int,
    current_params: MockParameters | Parameters,
) -> tuple[dict[str, Any], MockParameters | Parameters | None]:
    """Execute one FL round: fit all clients, aggregate, evaluate."""
    selected_clients = client_proxies[: min(num_clients, len(client_proxies))]

    fit_results: list[tuple[MockClientProxy, MockFitRes]] = []
    for client in selected_clients:
        fit_res = client.fit(current_params, {"round": round_num})
        fit_results.append((client, fit_res))

    aggregated_params = None
    fit_metrics: dict[str, Any] = {}
    try:
        result = strategy.aggregate_fit(
            server_round=round_num,
            results=fit_results,
            failures=[],
        )
        if result is not None:
            aggregated_params, fit_metrics = result
    except Exception as e:
        import logging

        logging.warning(f"aggregate_fit failed in round {round_num}: {e}")

    eval_results: list[tuple[MockClientProxy, MockEvaluateRes]] = []
    for client in selected_clients:
        eval_res = client.evaluate(current_params, {"round": round_num})
        eval_results.append((client, eval_res))

    avg_loss = 0.0
    eval_metrics: dict[str, Any] = {}
    try:
        result = strategy.aggregate_evaluate(
            server_round=round_num,
            results=eval_results,
            failures=[],
        )
        if result is not None:
            avg_loss, eval_metrics = result
            if avg_loss is None:
                avg_loss = 0.0
    except Exception as e:
        import logging

        logging.warning(f"aggregate_evaluate failed in round {round_num}: {e}")
        avg_loss = float(np.mean([res.loss for _, res in eval_results]))

    if "accuracy" not in eval_metrics:
        avg_accuracy = float(np.mean([res.metrics.get("accuracy", 0.0) for _, res in eval_results]))
        eval_metrics["accuracy"] = avg_accuracy

    return {
        "avg_loss": avg_loss,
        "metrics": {**eval_metrics, "num_clients": len(selected_clients)},
        "fit_results": fit_results,
        "eval_results": eval_results,
    }, aggregated_params


def mock_ndarrays_to_parameters(ndarrays: list[NDArray]) -> MockParameters:
    """Convert numpy arrays to MockParameters (serialized bytes)."""
    tensors = [arr.astype(np.float32).tobytes() for arr in ndarrays]
    return MockParameters(tensors, TENSOR_TYPE_NUMPY)


def mock_parameters_to_ndarrays(parameters: MockParameters) -> list[NDArray]:
    """Convert MockParameters back to list of numpy arrays."""
    return [np.frombuffer(tensor, dtype=np.float32) for tensor in parameters.tensors]


def mock_weighted_loss_avg(results: list[tuple[int, float]]) -> float:
    """Compute weighted average loss from (num_examples, loss) tuples."""
    if not results:
        return 0.0

    total_examples = sum(num_examples for num_examples, _ in results)
    if total_examples == 0:
        return 0.0

    weighted_sum = sum(num_examples * loss for num_examples, loss in results)
    return weighted_sum / total_examples


def create_mock_flower_client(client_id: int = 0) -> MockClient:
    """Factory for creating a MockClient with given ID."""
    numpy_client = MockNumPyClient(client_id)
    return MockClient(numpy_client)


def create_mock_client_proxies(num_clients: int) -> list[MockClientProxy]:
    """Create list of MockClientProxy instances with sequential IDs."""
    return [MockClientProxy(str(i)) for i in range(num_clients)]


def create_mock_fit_results(
    num_clients: int, param_shapes: list[tuple[int, ...]]
) -> list[MockFitRes]:
    """Generate deterministic fit results for testing aggregation.

    Args:
        num_clients: Number of result objects to create.
        param_shapes: Parameter tensor shapes (e.g., [(100, 10), (10,)]).

    Returns:
        List of MockFitRes with randomized but reproducible data.
    """
    results = []

    for client_id in range(num_clients):
        rng = np.random.default_rng(42 + client_id)

        tensors = []
        for shape in param_shapes:
            param = rng.standard_normal(shape).astype(np.float32)
            tensors.append(param.tobytes())

        parameters = MockParameters(tensors, TENSOR_TYPE_NUMPY)
        num_examples = int(rng.integers(50, 200))
        metrics: Metrics = {
            "loss": rng.uniform(0.1, 2.0),
            "accuracy": rng.uniform(0.5, 0.95),
        }

        results.append(MockFitRes(parameters, num_examples, metrics))

    return results


def create_mock_evaluate_results(num_clients: int) -> list[MockEvaluateRes]:
    """Generate deterministic evaluation results for testing.

    Args:
        num_clients: Number of result objects to create.

    Returns:
        List of MockEvaluateRes with randomized but reproducible data.
    """
    results = []

    for client_id in range(num_clients):
        rng = np.random.default_rng(42 + client_id)

        loss = rng.uniform(0.1, 1.5)
        num_examples = int(rng.integers(30, 100))
        metrics: Metrics = {
            "accuracy": rng.uniform(0.6, 0.95),
            "f1_score": rng.uniform(0.5, 0.9),
        }

        results.append(MockEvaluateRes(loss, num_examples, metrics))

    return results


def mock_run_simulation(
    server_app: Any,
    client_app: Any,
    num_supernodes: int,
    backend_config: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Mock the Flower 1.13+ run_simulation API for testing.

    Extracts strategy and client_fn from App objects and delegates
    to mock_start_simulation for actual execution.

    Args:
        server_app: ServerApp with server_fn attribute.
        client_app: ClientApp with client_fn attribute.
        num_supernodes: Number of virtual clients.
        backend_config: Ignored (compatibility only).
        **_kwargs: Ignored (compatibility only).

    Returns:
        Dict with simulation history (losses, metrics per round).
    """
    client_fn = getattr(client_app, "client_fn", None)
    if client_fn is None:
        raise ValueError("ClientApp must have client_fn attribute")

    server_fn = getattr(server_app, "server_fn", None)
    if server_fn is None:
        raise ValueError("ServerApp must have server_fn attribute")

    mock_context = type("Context", (), {"run_config": {}})()  # Minimal context stub
    server_components = server_fn(mock_context)

    strategy = getattr(server_components, "strategy", None)
    if strategy is None:
        raise ValueError("ServerAppComponents must have strategy attribute")

    config = getattr(server_components, "config", None)
    if config is None:
        config = MockServerConfig(10)

    return mock_start_simulation(
        client_fn=client_fn,
        num_clients=num_supernodes,
        config=config,
        strategy=strategy,
        initial_parameters=None,
    )
