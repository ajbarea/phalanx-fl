"""Mock Flower FL components for testing without distributed execution."""

from typing import Any, Callable, Optional, TypeAlias, Union

import numpy as np
from flwr.common import (
    Code,
    Parameters,
    Status,
    ndarrays_to_parameters,
    parameters_to_ndarrays,
)

NDArray: TypeAlias = np.ndarray
Config: TypeAlias = dict[str, Any]
Metrics: TypeAlias = dict[str, Any]
Scalar: TypeAlias = Union[bool, bytes, float, int, str]

TENSOR_TYPE_NUMPY = "numpy.ndarray"


class MockParameters:
    """Mock implementation of flwr.common.Parameters."""

    def __init__(self, tensors: list[bytes], tensor_type: str = TENSOR_TYPE_NUMPY):
        """Initializes mock parameters.

        Args:
            tensors: List of serialized tensors.
            tensor_type: Type of tensors.
        """
        self.tensors = tensors
        self.tensor_type = tensor_type

    def __eq__(self, other: object) -> bool:
        """Checks equality with another Parameters object."""
        if not isinstance(other, MockParameters):
            return False
        return self.tensors == other.tensors and self.tensor_type == other.tensor_type


class MockFitRes:
    """Mock implementation of flwr.common.FitRes."""

    def __init__(
        self,
        parameters: MockParameters,
        num_examples: int,
        metrics: Optional[Metrics] = None,
    ):
        """Initializes mock fit result.

        Args:
            parameters: Updated model parameters.
            num_examples: Number of training examples used.
            metrics: Optional training metrics.
        """
        self.status = Status(code=Code.OK, message="")
        self.parameters = parameters
        self.num_examples = num_examples
        self.metrics = metrics or {}


class MockEvaluateRes:
    """Mock implementation of flwr.common.EvaluateRes."""

    def __init__(self, loss: float, num_examples: int, metrics: Optional[Metrics] = None):
        """Initializes mock evaluation result.

        Args:
            loss: Evaluation loss.
            num_examples: Number of evaluation examples.
            metrics: Optional evaluation metrics.
        """
        self.status = Status(code=Code.OK, message="")
        self.loss = loss
        self.num_examples = num_examples
        self.metrics = metrics or {}


class MockClientProxy:
    """Mock implementation of flwr.server.client_proxy.ClientProxy."""

    def __init__(self, cid: str, client_fn: Optional[Callable[..., Any]] = None):
        """Initializes mock client proxy.

        Args:
            cid: Client ID.
            client_fn: Optional client function for creating actual client.
        """
        self.cid = cid
        self.client_fn = client_fn
        self._mock_client = None

        try:
            client_num = int(cid)
        except ValueError:
            client_num = hash(cid) % 1000
        self._rng = np.random.default_rng(42 + client_num)
        self._training_rounds = 0

    def fit(self, parameters: Any, _: Config) -> MockFitRes:
        """Simulates client training.

        Args:
            parameters: Model parameters from server.
            _: Training configuration.

        Returns:
            Mock fit result with updated parameters and metrics.
        """
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
        """Simulates client evaluation.

        Args:
            _parameters: Model parameters from server.
            _config: Evaluation configuration.

        Returns:
            Mock evaluation result.
        """
        mock_loss = self._rng.uniform(0.1, 1.5)
        mock_accuracy = self._rng.uniform(0.6, 0.95)
        num_examples = int(self._rng.integers(30, 100))

        metrics: Metrics = {
            "accuracy": mock_accuracy,
            "f1_score": self._rng.uniform(0.5, 0.9),
        }

        return MockEvaluateRes(mock_loss, num_examples, metrics)


class MockServerConfig:
    """Mock implementation of flwr.server.ServerConfig."""

    def __init__(self, num_rounds: int):
        """Initializes mock server configuration.

        Args:
            num_rounds: Number of federated learning rounds.
        """
        self.num_rounds = num_rounds


class MockNumPyClient:
    """Mock implementation of flwr.client.NumPyClient."""

    def __init__(self, client_id: int = 0):
        """Initializes mock NumPy client.

        Args:
            client_id: Client identifier.
        """
        self.client_id = client_id
        self._rng = np.random.default_rng(42 + client_id)

    def get_parameters(self, _: Config) -> list[NDArray]:
        """Gets client parameters.

        Args:
            _: Configuration dictionary.

        Returns:
            List of parameter arrays.
        """
        self._rng = np.random.default_rng(42 + self.client_id)
        return [
            self._rng.standard_normal((100, 10)).astype(np.float32),
            self._rng.standard_normal(10).astype(np.float32),
        ]

    def fit(self, parameters: list[NDArray], _: Config) -> tuple[list[NDArray], int, Metrics]:
        """Simulates client training.

        Args:
            parameters: Model parameters from server.
            _: Training configuration.

        Returns:
            Tuple of (updated_parameters, num_examples, metrics).
        """
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
        """Simulates client evaluation.

        Args:
            _parameters: Model parameters from server.
            _config: Evaluation configuration.

        Returns:
            Tuple of (loss, num_examples, metrics).
        """
        loss = self._rng.uniform(0.1, 1.5)
        num_examples = int(self._rng.integers(30, 100))
        metrics: Metrics = {
            "accuracy": self._rng.uniform(0.6, 0.95),
            "f1_score": self._rng.uniform(0.5, 0.9),
        }

        return loss, num_examples, metrics


class MockClient:
    """Mock implementation of flwr.client.Client."""

    def __init__(self, numpy_client: MockNumPyClient):
        """Initializes mock client wrapper.

        Args:
            numpy_client: Underlying NumPy client.
        """
        self.numpy_client = numpy_client

    def fit(self, parameters: MockParameters, config: Config) -> MockFitRes:
        """Delegates fit to NumPy client."""
        np_params = [np.frombuffer(t, dtype=np.float32) for t in parameters.tensors]

        updated_params, num_examples, metrics = self.numpy_client.fit(np_params, config)

        updated_tensors = [p.tobytes() for p in updated_params]
        updated_parameters = MockParameters(updated_tensors, parameters.tensor_type)

        return MockFitRes(updated_parameters, num_examples, metrics)

    def evaluate(self, parameters: MockParameters, config: Config) -> MockEvaluateRes:
        """Delegates evaluate to NumPy client."""
        np_params = [np.frombuffer(t, dtype=np.float32) for t in parameters.tensors]

        loss, num_examples, metrics = self.numpy_client.evaluate(np_params, config)

        return MockEvaluateRes(loss, num_examples, metrics)


def mock_start_simulation(
    client_fn: Callable[[str], MockClient],
    num_clients: int,
    config: MockServerConfig,
    strategy: Any,
    initial_parameters: Optional[Union[MockParameters, Parameters]] = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Mocks flwr.simulation.start_simulation with real strategy execution.

    Args:
        client_fn: Function to create client instances.
        num_clients: Number of clients in simulation.
        config: Server configuration.
        strategy: Aggregation strategy instance.
        initial_parameters: Initial model parameters for simulation.
        **_kwargs: Additional simulation parameters.

    Returns:
        Mock simulation results.
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
    current_params: Union[MockParameters, Parameters],
) -> tuple[dict[str, Any], Optional[Union[MockParameters, Parameters]]]:
    """Simulates a single federated learning round.

    Args:
        client_proxies: List of client proxies.
        strategy: Aggregation strategy instance.
        round_num: Current round number.
        num_clients: Total number of clients.
        current_params: Current model parameters.

    Returns:
        Tuple of (round_results_dict, aggregated_parameters).
    """
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
    """Mocks flwr.common.ndarrays_to_parameters.

    Args:
        ndarrays: List of numpy arrays.

    Returns:
        Mock Parameters object.
    """
    tensors = [arr.astype(np.float32).tobytes() for arr in ndarrays]
    return MockParameters(tensors, TENSOR_TYPE_NUMPY)


def mock_parameters_to_ndarrays(parameters: MockParameters) -> list[NDArray]:
    """Mocks flwr.common.parameters_to_ndarrays.

    Args:
        parameters: Mock Parameters object.

    Returns:
        List of numpy arrays.
    """
    return [np.frombuffer(tensor, dtype=np.float32) for tensor in parameters.tensors]


def mock_weighted_loss_avg(results: list[tuple[int, float]]) -> float:
    """Mocks flwr.server.strategy.aggregate.weighted_loss_avg.

    Args:
        results: List of (num_examples, loss) tuples.

    Returns:
        Weighted average loss.
    """
    if not results:
        return 0.0

    total_examples = sum(num_examples for num_examples, _ in results)
    if total_examples == 0:
        return 0.0

    weighted_sum = sum(num_examples * loss for num_examples, loss in results)
    return weighted_sum / total_examples


def create_mock_flower_client(client_id: int = 0) -> MockClient:
    """Creates a mock Flower client.

    Args:
        client_id: Client identifier.

    Returns:
        Mock Flower client.
    """
    numpy_client = MockNumPyClient(client_id)
    return MockClient(numpy_client)


def create_mock_client_proxies(num_clients: int) -> list[MockClientProxy]:
    """Creates multiple mock client proxies.

    Args:
        num_clients: Number of client proxies to create.

    Returns:
        List of mock client proxies.
    """
    return [MockClientProxy(str(i)) for i in range(num_clients)]


def create_mock_fit_results(
    num_clients: int, param_shapes: list[tuple[int, ...]]
) -> list[MockFitRes]:
    """Creates mock fit results.

    Args:
        num_clients: Number of clients.
        param_shapes: Shapes of model parameters.

    Returns:
        List of mock fit results.
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
    """Creates mock evaluation results.

    Args:
        num_clients: Number of clients.

    Returns:
        List of mock evaluation results.
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
