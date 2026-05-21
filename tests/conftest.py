"""Pytest configuration and fixtures for federated learning simulation tests.

This module provides:
- Root-level fixtures shared across all test files
- Advanced parameterization patterns (indirect, dynamic)
- Autouse fixtures for test isolation
- Failure logging hooks for debugging

For fixture architecture details, see demo/TESTING.md
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from tests.common import ATTACK_TYPES, DEFENSE_STRATEGIES, STRATEGY_CONFIGS, np

os.environ["LOKY_MAX_CPU_COUNT"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"


# =============================================================================
# DYNAMIC TEST GENERATION HOOK
# =============================================================================


def pytest_generate_tests(metafunc):
    """Dynamically generate test parameters based on fixture names.

    This hook enables dynamic test parameterization at collection time.
    Tests can request specific fixture names to receive dynamic parameters.

    Supported fixtures:
    - attack_defense_combo: All (attack_type, defense_strategy) combinations
    - strategy_variant: All strategy configurations from STRATEGY_CONFIGS
    """
    # Generate attack × defense combinatorial tests
    if "attack_defense_combo" in metafunc.fixturenames:
        combos = [
            (attack, defense)
            for attack in ATTACK_TYPES[:6]  # Limit to main attack types
            for defense in DEFENSE_STRATEGIES
        ]
        metafunc.parametrize(
            "attack_defense_combo",
            combos,
            ids=[f"{a}-vs-{d}" for a, d in combos],
        )

    # Generate strategy variant tests
    if "strategy_variant" in metafunc.fixturenames:
        strategies = list(STRATEGY_CONFIGS.keys())
        metafunc.parametrize(
            "strategy_variant",
            strategies,
            ids=[f"strategy-{s}" for s in strategies],
        )


# =============================================================================
# INDIRECT PARAMETERIZATION FIXTURES
# =============================================================================


@pytest.fixture
def attack_scenario(request) -> dict[str, Any]:
    """Fixture for indirect parameterization of attack scenarios.

    Usage:
        @pytest.mark.parametrize(
            "attack_scenario",
            [("gaussian_noise", 2), ("model_poisoning", 3)],
            indirect=True,
        )
        def test_with_attack(attack_scenario):
            # attack_scenario contains full setup

    Args:
        request: pytest request with param tuple (attack_type, num_byzantine)

    Returns:
        Dict with attack configuration and generated parameters
    """
    from tests.fixtures.mock_datasets import generate_byzantine_client_parameters

    attack_type, num_byzantine = request.param
    num_clients = max(10, num_byzantine * 3)  # Ensure enough honest clients
    param_size = 500

    return {
        "attack_type": attack_type,
        "num_byzantine": num_byzantine,
        "num_clients": num_clients,
        "param_size": param_size,
        "attack_params": generate_byzantine_client_parameters(
            num_clients=num_clients,
            num_byzantine=num_byzantine,
            param_size=param_size,
            attack_type=attack_type,
        ),
    }


@pytest.fixture
def defense_config(request) -> dict[str, Any]:
    """Fixture for indirect parameterization of defense strategies.

    Usage:
        @pytest.mark.parametrize(
            "defense_config",
            ["krum", "bulyan", "trimmed_mean"],
            indirect=True,
        )
        def test_with_defense(defense_config):
            # defense_config contains full strategy configuration

    Args:
        request: pytest request with strategy name

    Returns:
        Dict with full strategy configuration
    """
    strategy_name = request.param
    if strategy_name not in DEFENSE_STRATEGIES:
        pytest.skip(f"Unknown defense strategy: {strategy_name}")
    return {
        "name": strategy_name,
        **DEFENSE_STRATEGIES[strategy_name],
    }


# =============================================================================
# ATTACK SNAPSHOT PARAMETERIZED FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def sample_tensors_factory() -> Callable:
    """Factory for creating sample tensors with various configurations.

    Returns:
        Callable that creates (data, labels) tensors with specified parameters
    """
    from tests.common import create_sample_tensors

    def _create(
        batch_size: int = 5,
        image_shape: tuple = (1, 28, 28),
        num_classes: int = 10,
    ) -> tuple[Any, Any]:
        return create_sample_tensors(
            batch_size=batch_size,
            image_shape=image_shape,
            num_classes=num_classes,
        )

    return _create


@pytest.fixture(params=ATTACK_TYPES[:6])  # Main attack types
def attack_type_param(request) -> str:
    """Parameterized fixture providing each attack type."""
    return request.param


@pytest.fixture(params=list(DEFENSE_STRATEGIES.keys()))
def defense_strategy_param(request) -> str:
    """Parameterized fixture providing each defense strategy name."""
    return request.param


@pytest.fixture(params=[(5, 3), (10, 5), (3, 10)])
def batch_max_samples_combo(request) -> tuple[int, int]:
    """Parameterized fixture for batch_size × max_samples combinations.

    Yields:
        Tuple of (batch_size, max_samples)
    """
    return request.param


@pytest.fixture
def mock_output_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Returns a temporary output directory with DirectoryHandler mocked."""
    output_dir = tmp_path / "out" / "test_run"
    output_dir.mkdir(parents=True)
    (output_dir / "output.log").touch()

    monkeypatch.setattr(
        "intellifl.output_handlers.directory_handler.DirectoryHandler.dirname",
        str(output_dir),
    )

    return output_dir


@pytest.fixture(autouse=True, scope="function")
def prevent_real_output_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirects DirectoryHandler output to tmp_path."""
    test_output = tmp_path / "test_output"
    test_output.mkdir()
    csv_dir = test_output / "csv"
    csv_dir.mkdir()

    monkeypatch.setattr(
        "intellifl.output_handlers.directory_handler.DirectoryHandler.dirname",
        str(test_output),
    )


@pytest.fixture(scope="session")
def mock_strategy_configs() -> dict[str, dict[str, Any]]:
    """Returns strategy configurations for parameterized tests."""
    return STRATEGY_CONFIGS


@pytest.fixture
def strategy_history():
    """
    Reusable SimulationStrategyHistory mock fixture.

    Provides pre-configured mock with common methods stubbed.
    """
    from unittest.mock import MagicMock

    from intellifl.data_models.simulation_strategy_history import SimulationStrategyHistory

    history = MagicMock(spec=SimulationStrategyHistory)
    history.insert_round_history_entry = MagicMock()
    history.insert_single_client_history_entry = MagicMock()
    history.get_round_history = MagicMock(return_value=[])
    history.get_client_history = MagicMock(return_value=[])
    return history


@pytest.fixture(params=["trust", "pid", "krum", "multi-krum", "trimmed_mean"])
def strategy_config(
    request: pytest.FixtureRequest, mock_strategy_configs: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Returns parameterized strategy configuration."""
    return mock_strategy_configs[request.param]


@pytest.fixture(params=["bloodmnist", "femnist_iid", "pneumoniamnist", "bloodmnist"])
def dataset_type(request: pytest.FixtureRequest) -> str:
    """Returns parameterized dataset type."""
    return str(request.param)


@pytest.fixture
def temp_dataset_dir(tmp_path: Path) -> Path:
    """Returns a temporary dataset directory with mock data files."""
    dataset_dir = tmp_path / "datasets"
    dataset_dir.mkdir()
    (dataset_dir / "train.txt").write_text("mock training data")
    (dataset_dir / "test.txt").write_text("mock test data")
    return dataset_dir


@pytest.fixture
def mock_client_parameters():
    """Returns a list of random client parameter arrays."""
    rng = np.random.default_rng(42)
    return [rng.standard_normal(100) for _ in range(5)]


@pytest.fixture
def medquad_column_names():
    """Returns standard column names for MedQuAD dataset mocks."""
    return ["input_ids", "attention_mask", "answer", "token_type_ids", "question"]


@pytest.fixture
def mock_dataset_dict_chain(medquad_column_names):
    """Returns a DatasetDict mock with method chaining support."""
    from unittest.mock import Mock

    mock_dataset_dict = Mock()
    mock_train_dataset = Mock()
    mock_train_dataset.column_names = medquad_column_names

    mock_dataset_dict.map.return_value = mock_dataset_dict
    mock_dataset_dict.remove_columns.return_value = mock_dataset_dict
    mock_dataset_dict.__getitem__ = Mock(return_value=mock_train_dataset)
    mock_train_dataset.train_test_split.return_value = {
        "train": Mock(),
        "test": Mock(),
    }

    return mock_dataset_dict, mock_train_dataset


@pytest.fixture
def sample_attack_data():
    """Returns sample data and label tensors for attack snapshot tests."""
    from tests.common import create_sample_tensors

    data, labels = create_sample_tensors(batch_size=5)
    return data, labels, labels.clone()


@pytest.fixture
def attack_config_label_flipping():
    """Returns a label flipping attack configuration."""
    from tests.common import create_attack_config

    return create_attack_config("label_flipping")


@pytest.fixture
def attack_config_gaussian_noise():
    """Returns a gaussian noise attack configuration."""
    from tests.common import create_attack_config

    return create_attack_config("gaussian_noise", target_noise_snr=10.0)


@pytest.fixture
def nested_attack_config():
    """Returns a nested attack configuration."""
    from tests.common import create_nested_attack_config

    return create_nested_attack_config("label_flipping")


failure_logger = logging.getLogger("test_failure_helper")


def _setup_failure_logger():
    """Configures the failure logger with file handler."""
    if not failure_logger.handlers:
        failure_logger.setLevel(logging.INFO)
        failure_logger.propagate = False

        log_dir = Path("tests/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"test_failures_{timestamp}.log"

        fh = logging.FileHandler(log_file, mode="w")
        fh.setLevel(logging.INFO)

        formatter = logging.Formatter("%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        fh.setFormatter(formatter)

        failure_logger.addHandler(fh)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Logs context-specific hints for test failures."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        _setup_failure_logger()

        excinfo = call.excinfo
        if excinfo:
            exc_type = excinfo.type
            exc_message = str(excinfo.value)
            test_path = item.fspath.strpath

            header = f"Test Failed: {item.nodeid}"
            separator = "-" * len(header)
            failure_logger.info(separator)
            failure_logger.info(header)
            failure_logger.info(f"Exception: {exc_type.__name__}")

            if issubclass(exc_type, ImportError):
                failure_logger.warning(
                    "Hint: An ImportError often means a problem with your environment."
                )
                failure_logger.warning(
                    "  - Did you forget to activate the virtual environment? (`source venv/Scripts/activate`)"
                )
                failure_logger.warning(
                    "  - Are you running pytest from the project root directory?"
                )

            elif issubclass(exc_type, FileNotFoundError):
                failure_logger.warning(
                    "Hint: A FileNotFoundError suggests a missing file or incorrect path."
                )
                failure_logger.warning("  - If loading data, check that the path is correct.")
                failure_logger.warning(
                    "  - Are you using a temporary directory fixture (e.g., `tmp_path`) correctly?"
                )

            elif issubclass(exc_type, RuntimeError) and (
                "shape" in exc_message or "dimension" in exc_message
            ):
                failure_logger.warning(
                    "Hint: A RuntimeError mentioning 'shape' or 'dimension' is a common PyTorch error."
                )
                failure_logger.warning(
                    "  - Your tensor dimensions might not match. Check the model's input/output shapes."
                )
                failure_logger.warning(
                    "  - See `tests/docs/test_data_generation.md` to verify mock data shapes."
                )

            elif "test_simulation_strategies" in test_path and issubclass(exc_type, AssertionError):
                failure_logger.warning(
                    "Hint: An AssertionError in a strategy test points to an algorithmic problem."
                )
                failure_logger.warning(
                    "  - Does your aggregation logic handle this edge case correctly?"
                )
                failure_logger.warning(
                    "  - Review the core concepts in `tests/docs/fl_fundamentals.md`."
                )

            elif issubclass(exc_type, AssertionError):
                failure_logger.warning(
                    "Hint: An AssertionError means a condition you expected to be true was false."
                )
                failure_logger.warning(
                    "  - Double-check the values being compared in your `assert` statement."
                )

            failure_logger.info(separator)
