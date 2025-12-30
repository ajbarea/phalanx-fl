import csv
import datetime
import json
import os
from pathlib import Path

from src.data_models.client_info import ClientInfo
from src.data_models.round_info import RoundsInfo
from src.data_models.simulation_strategy_config import StrategyConfig
from src.data_models.simulation_strategy_history import SimulationStrategyHistory
from src.dataset_handlers.dataset_handler import DatasetHandler
from src.output_handlers.directory_handler import DirectoryHandler
from tests.common import Mock, pytest


class TestDirectoryHandler:
    """Tests for DirectoryHandler output functionality."""

    @pytest.fixture
    def mock_strategy_config(self):
        """Returns a mock StrategyConfig."""
        return StrategyConfig(
            aggregation_strategy_keyword="trust",
            num_of_rounds=3,
            num_of_clients=5,
            strategy_number=1,
            trust_threshold=0.7,
            remove_clients=True,
        )

    @pytest.fixture
    def mock_client_info_list(self):
        """Returns a list of mock ClientInfo objects with metrics."""
        clients = []
        for i in range(3):
            client = ClientInfo(client_id=i, num_of_rounds=3)
            client.loss_history = [0.5 + i * 0.1, 0.4 + i * 0.1, 0.3 + i * 0.1]
            client.accuracy_history = [0.8 - i * 0.05, 0.85 - i * 0.05, 0.9 - i * 0.05]
            clients.append(client)
        return clients

    @pytest.fixture
    def mock_round_info_list(self):
        """Returns a list of mock round info objects."""
        rounds = []
        for i in range(3):
            round_info = Mock()
            round_info.round_number = i + 1
            round_info.aggregated_loss = 0.5 - i * 0.1
            round_info.aggregated_accuracy = 0.8 + i * 0.05
            rounds.append(round_info)
        return rounds

    @pytest.fixture
    def mock_simulation_history(
        self, mock_strategy_config, mock_client_info_list, mock_round_info_list
    ):
        """Returns a mock SimulationStrategyHistory."""

        mock_dataset_handler = Mock(spec=DatasetHandler)
        mock_dataset_handler.poisoned_client_ids = set()

        mock_rounds = Mock(spec=RoundsInfo)
        mock_rounds.savable_metrics = [
            "score_calculation_time_nanos_history",
            "removal_threshold_history",
            "aggregated_loss_history",
            "average_accuracy_history",
        ]
        mock_rounds.statsable_metrics = [
            "aggregated_loss_history",
            "average_accuracy_history",
        ]

        def get_metric(name):
            if name == "aggregated_loss_history":
                return [r.aggregated_loss for r in mock_round_info_list]
            if name == "average_accuracy_history":
                return [r.aggregated_accuracy for r in mock_round_info_list]
            return []

        mock_rounds.get_metric_by_name.side_effect = get_metric

        history = SimulationStrategyHistory(
            strategy_config=mock_strategy_config,
            dataset_handler=mock_dataset_handler,
        )
        history.rounds_history = mock_rounds
        history.get_all_clients = Mock(return_value=mock_client_info_list)  # type: ignore[method-assign]
        return history

    def test_init_creates_directories(self, tmp_path):
        """Verifies initialization creates required directories."""
        test_dir = tmp_path / "test_output"
        handler = DirectoryHandler(output_dir=str(test_dir))

        assert handler.dirname is not None
        assert Path(handler.dirname).exists()
        assert handler.new_csv_dirname is not None
        assert Path(handler.new_csv_dirname).exists()
        assert handler.simulation_strategy_history is None
        assert handler.dataset_dir is None

    def test_assign_dataset_dir(self, tmp_path):
        """Verifies assign_dataset_dir creates dataset directory."""
        test_dir = tmp_path / "test_output"
        handler = DirectoryHandler(output_dir=str(test_dir))

        handler.assign_dataset_dir(1)

        assert handler.dataset_dir is not None
        assert handler.dataset_dir.endswith("/dataset_1") or handler.dataset_dir.endswith(
            "\\dataset_1"
        )
        assert Path(handler.dataset_dir).exists()

    def test_save_csv_and_config_calls_all_save_methods(self, mock_simulation_history, tmp_path):
        """Verifies save_csv_and_config creates all expected output files."""
        test_dir = tmp_path / "test_output"
        handler = DirectoryHandler(output_dir=str(test_dir))

        handler.save_csv_and_config(mock_simulation_history)

        assert handler.dirname is not None
        config_file = Path(handler.dirname) / "strategy_config_1.json"
        assert config_file.exists()

        assert handler.new_csv_dirname is not None
        csv_dir = Path(handler.new_csv_dirname)
        client_csv = csv_dir / "per_client_metrics_1.csv"
        round_csv = csv_dir / "round_metrics_1.csv"
        execution_csv = csv_dir / "exec_stats_1.csv"

        assert client_csv.exists()
        assert round_csv.exists()
        assert execution_csv.exists()

    def test_save_simulation_config_creates_json_file(self, mock_simulation_history, tmp_path):
        """Verifies _save_simulation_config creates valid JSON with expected fields."""
        test_dir = tmp_path / "config_test"
        handler = DirectoryHandler(output_dir=str(test_dir))
        handler.simulation_strategy_history = mock_simulation_history

        handler._save_simulation_config()

        assert handler.dirname is not None
        config_file = Path(handler.dirname) / "strategy_config_1.json"
        assert config_file.exists()

        with open(config_file) as f:
            saved_config = json.load(f)

        assert saved_config["aggregation_strategy_keyword"] == "trust"
        assert saved_config["num_of_rounds"] == 3
        assert saved_config["strategy_number"] == 1

    def test_save_per_client_to_csv_creates_correct_format(self, mock_simulation_history, tmp_path):
        """Verifies _save_per_client_to_csv creates CSV with expected headers and rows."""
        test_dir = tmp_path / "csv_test"
        handler = DirectoryHandler(output_dir=str(test_dir))
        handler.simulation_strategy_history = mock_simulation_history

        handler._save_per_client_to_csv()

        assert handler.new_csv_dirname is not None
        csv_file = Path(handler.new_csv_dirname) / "per_client_metrics_1.csv"
        assert csv_file.exists()

        with open(csv_file) as f:
            reader = csv.reader(f)
            headers = next(reader)

            assert headers[0] == "round"
            assert "client_0_loss_history" in headers
            assert "client_0_accuracy_history" in headers

            rows = list(reader)
            assert len(rows) == 3

    def test_save_per_client_to_csv_handles_missing_metrics(self, mock_strategy_config, tmp_path):
        """Verifies _save_per_client_to_csv handles clients with missing metrics."""

        client_with_missing_metrics = ClientInfo(
            client_id=0, num_of_rounds=mock_strategy_config.num_of_rounds
        )

        mock_dataset_handler = Mock(spec=DatasetHandler)
        mock_dataset_handler.poisoned_client_ids = set()

        history = SimulationStrategyHistory(
            strategy_config=mock_strategy_config,
            dataset_handler=mock_dataset_handler,
        )
        history.rounds_history = Mock(spec=RoundsInfo)
        history.get_all_clients = Mock(return_value=[client_with_missing_metrics])  # type: ignore[method-assign]

        test_dir = tmp_path / "csv_missing_test"
        handler = DirectoryHandler(output_dir=str(test_dir))
        handler.simulation_strategy_history = history

        handler._save_per_client_to_csv()

        assert handler.new_csv_dirname is not None
        csv_file = Path(handler.new_csv_dirname) / "per_client_metrics_1.csv"
        assert csv_file.exists()

        with open(csv_file) as f:
            reader = csv.reader(f)
            headers = next(reader)
            rows = list(reader)

            loss_col_index = headers.index("client_0_loss_history")
            agg_part_col_index = headers.index("client_0_aggregation_participation_history")

            for row in rows:
                assert row[loss_col_index] == "not collected"
                assert row[agg_part_col_index] == "1"

    def test_save_per_round_to_csv_creates_correct_format(self, mock_simulation_history, tmp_path):
        """Verifies _save_per_round_to_csv creates CSV with expected headers."""
        test_dir = tmp_path / "round_csv_test"
        handler = DirectoryHandler(output_dir=str(test_dir))
        handler.simulation_strategy_history = mock_simulation_history

        handler._save_per_round_to_csv()

        assert handler.new_csv_dirname is not None
        csv_file = Path(handler.new_csv_dirname) / "round_metrics_1.csv"
        assert csv_file.exists()

        with open(csv_file) as f:
            reader = csv.reader(f)
            headers = next(reader)

            assert headers[0] == "round"
            assert "aggregated_loss_history" in headers
            assert "average_accuracy_history" in headers

    def test_save_per_execution_to_csv_creates_file(self, mock_simulation_history, tmp_path):
        """Verifies _save_per_execution_to_csv creates the execution stats file."""
        test_dir = tmp_path / "execution_csv_test"
        handler = DirectoryHandler(output_dir=str(test_dir))
        handler.simulation_strategy_history = mock_simulation_history

        handler._save_per_execution_to_csv()

        assert handler.new_csv_dirname is not None
        csv_file = Path(handler.new_csv_dirname) / "exec_stats_1.csv"
        assert csv_file.exists()

    def test_directory_naming_uses_timestamp(self, tmp_path, monkeypatch):
        """Verifies directory names include timestamp when no output_dir provided."""
        mock_now = Mock()
        mock_now.strftime.return_value = "01-01-2024_12-00-00"
        monkeypatch.setattr(datetime, "datetime", Mock(now=Mock(return_value=mock_now)))

        handler = DirectoryHandler()
        assert handler.dirname is not None
        assert f"out{os.sep}" in handler.dirname

    def test_csv_dirname_is_subdirectory_of_dirname(self, tmp_path):
        """Verifies CSV directory is a subdirectory of main directory."""
        test_dir = tmp_path / "test_dir"
        handler = DirectoryHandler(output_dir=str(test_dir))

        assert handler.dirname is not None
        assert handler.new_csv_dirname == str(Path(handler.dirname) / "csv")
