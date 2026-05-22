from __future__ import annotations

import json
from unittest.mock import patch

import matplotlib

from intellifl.data_models.client_info import ClientInfo
from intellifl.data_models.round_info import RoundsInfo
from intellifl.data_models.simulation_strategy_config import StrategyConfig
from intellifl.data_models.simulation_strategy_history import SimulationStrategyHistory
from intellifl.federated_simulation import FederatedSimulation
from intellifl.output_handlers.new_plot_handler import (
    ATTACK_ABBREV,
    _add_attack_background_shading,
    _generate_multi_string_strategy_label,
    _generate_single_string_strategy_label,
    _get_client_attack_summary,
    _is_client_malicious,
    bar_width,
    plot_size,
    save_plot_data_json,
    show_inter_strategy_plots,
    show_plots_within_strategy,
)
from tests.common import Mock, np, pytest

matplotlib.use("Agg")


class TestPlotHandler:
    """Tests for new_plot_handler plotting functionality."""

    @pytest.fixture
    def mock_strategy_config(self):
        """Returns a mock StrategyConfig."""
        return StrategyConfig(
            aggregation_strategy_keyword="trust",
            dataset_keyword="bloodmnist",
            remove_clients=True,
            begin_removing_from_round=2,
            num_of_clients=10,
            num_of_malicious_clients=2,
            num_of_client_epochs=3,
            batch_size=32,
            show_plots=True,
            save_plots=False,
        )

    @pytest.fixture
    def mock_client_info_list(self):
        """Returns mock ClientInfo objects with loss and accuracy metrics."""
        clients = []
        for i in range(3):
            client = ClientInfo(client_id=i, num_of_rounds=3)
            client.loss_history = [0.8 - i * 0.1, 0.6 - i * 0.1, 0.4 - i * 0.1]
            client.accuracy_history = [0.6 + i * 0.1, 0.7 + i * 0.1, 0.8 + i * 0.1]
            clients.append(client)
        return clients

    @pytest.fixture
    def mock_simulation_strategy(self, mock_strategy_config, mock_client_info_list):
        """Returns a mock FederatedSimulation with strategy history."""

        simulation = Mock(spec=FederatedSimulation)
        simulation.strategy_config = mock_strategy_config

        strategy_history = Mock(spec=SimulationStrategyHistory)
        strategy_history.get_all_clients.return_value = mock_client_info_list

        mock_rounds_history = Mock(spec=RoundsInfo)
        mock_rounds_history.removal_threshold_history = []
        mock_rounds_history.average_accuracy_history = []
        mock_rounds_history.aggregated_loss_history = []
        mock_rounds_history.average_accuracy_std_history = []
        strategy_history.rounds_history = mock_rounds_history

        simulation.strategy_history = strategy_history

        return simulation

    @pytest.fixture
    def mock_directory_handler(self, tmp_path):
        """Returns a mock directory handler with tmp_path outputs."""
        test_output = tmp_path / "test_output"
        test_output.mkdir(exist_ok=True)
        handler = Mock()
        handler.dirname = str(test_output)
        handler.new_plots_dirname = str(test_output)
        return handler

    def test_generate_single_string_strategy_label(self, mock_strategy_config):
        """Verifies _generate_single_string_strategy_label includes all config fields."""
        label = _generate_single_string_strategy_label(mock_strategy_config)

        assert "strategy: trust" in label
        assert "dataset: bloodmnist" in label
        assert "remove: True" in label
        assert "remove_from: 2" in label
        assert "total clients: 10" in label
        assert "bad_clients: 2" in label
        assert "client_epochs: 3" in label
        assert "batch_size: 32" in label

    def test_generate_single_string_strategy_label_no_removal(self):
        """Verifies label shows 'n/a' for remove_from when removal is disabled."""
        config = StrategyConfig(
            aggregation_strategy_keyword="fedavg",
            dataset_keyword="femnist",
            remove_clients=False,
            num_of_clients=5,
            num_of_malicious_clients=0,
            num_of_client_epochs=1,
            batch_size=16,
        )

        label = _generate_single_string_strategy_label(config)

        assert "remove: False" in label
        assert "remove_from: n/a" in label

    def test_generate_multi_string_strategy_label(self, mock_strategy_config):
        """Verifies multi-string label replaces commas with newlines."""
        multi_label = _generate_multi_string_strategy_label(mock_strategy_config)
        single_label = _generate_single_string_strategy_label(mock_strategy_config)

        assert multi_label == single_label.replace(", ", "\n")
        assert "\n" in multi_label
        assert ", " not in multi_label

    def test_show_plots_within_strategy_returns_early_when_no_plots_enabled(
        self, mock_simulation_strategy, mock_directory_handler
    ):
        """Verifies no plots are created when both show and save are disabled."""
        mock_simulation_strategy.strategy_config.show_plots = False
        mock_simulation_strategy.strategy_config.save_plots = False

        with patch("matplotlib.pyplot.subplots") as mock_subplots:
            show_plots_within_strategy(mock_simulation_strategy, mock_directory_handler)

            mock_subplots.assert_not_called()

    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.savefig")
    def test_show_plots_within_strategy_creates_plots_when_enabled(
        self,
        mock_savefig,
        mock_show,
        mock_figure,
        mock_simulation_strategy,
        mock_directory_handler,
    ):
        """Verifies plots are created and shown when show_plots is enabled."""
        mock_simulation_strategy.strategy_config.show_plots = True
        mock_simulation_strategy.strategy_config.save_plots = False

        show_plots_within_strategy(mock_simulation_strategy, mock_directory_handler)

        mock_figure.assert_called()
        mock_show.assert_called()

    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.savefig")
    def test_show_plots_within_strategy_saves_plots_when_enabled(
        self,
        mock_savefig,
        mock_show,
        mock_figure,
        mock_simulation_strategy,
        mock_directory_handler,
    ):
        """Verifies plots are saved but not shown when only save_plots is enabled."""
        mock_simulation_strategy.strategy_config.save_plots = True
        mock_simulation_strategy.strategy_config.show_plots = False

        show_plots_within_strategy(mock_simulation_strategy, mock_directory_handler)

        mock_figure.assert_called()
        mock_savefig.assert_called()
        mock_show.assert_not_called()

    @patch("matplotlib.pyplot.subplots")
    def test_show_plots_within_strategy_handles_empty_client_list(
        self, mock_subplots, mock_simulation_strategy, mock_directory_handler
    ):
        """Verifies empty client list does not raise an exception."""
        mock_simulation_strategy.strategy_history.get_all_clients.return_value = []

        mock_fig = Mock()
        mock_axes = [Mock(), Mock()]
        mock_subplots.return_value = (mock_fig, mock_axes)

        show_plots_within_strategy(mock_simulation_strategy, mock_directory_handler)

    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.plot")
    def test_show_plots_within_strategy_uses_client_metrics(
        self, mock_plot, mock_figure, mock_simulation_strategy, mock_directory_handler
    ):
        """Verifies client loss and accuracy metrics are plotted."""
        show_plots_within_strategy(mock_simulation_strategy, mock_directory_handler)

        mock_plot.assert_called()

    def test_plot_size_constant(self):
        """Verifies plot_size is a tuple of two integers."""
        assert plot_size == (11, 7)
        assert len(plot_size) == 2
        assert all(isinstance(dim, int) for dim in plot_size)

    def test_bar_width_constant(self):
        """Verifies bar_width is a positive float."""
        assert bar_width == 0.2
        assert isinstance(bar_width, float)

    @patch("matplotlib.pyplot.subplots")
    def test_show_plots_with_both_options_enabled(
        self, mock_subplots, mock_simulation_strategy, mock_directory_handler
    ):
        """Verifies both show and save occur when both options are enabled."""
        mock_fig = Mock()
        mock_axes = [Mock(), Mock()]
        mock_subplots.return_value = (mock_fig, mock_axes)

        mock_simulation_strategy.strategy_config.show_plots = True
        mock_simulation_strategy.strategy_config.save_plots = True

        with patch("matplotlib.pyplot.show") as mock_show:
            with patch("matplotlib.pyplot.savefig") as mock_savefig:
                show_plots_within_strategy(mock_simulation_strategy, mock_directory_handler)

                mock_show.assert_called()
                mock_savefig.assert_called()

    def test_strategy_label_handles_none_values(self):
        """Verifies None values in config are converted to strings."""
        config = StrategyConfig(
            aggregation_strategy_keyword="fedavg",
            dataset_keyword=None,
            num_of_clients=None,
            num_of_client_epochs=None,
            batch_size=None,
        )

        label = _generate_single_string_strategy_label(config)
        assert "strategy: fedavg" in label
        assert "None" in label

    @pytest.fixture
    def mock_multiple_strategies(self, mock_strategy_config):
        """Returns multiple mock FederatedSimulation objects for inter-strategy tests."""
        strategies = []
        for i in range(2):
            simulation = Mock(spec=FederatedSimulation)
            config = StrategyConfig(
                aggregation_strategy_keyword=f"strategy_{i}",
                dataset_keyword="test_dataset",
                remove_clients=i % 2 == 0,
                num_of_clients=5 + i,
                num_of_malicious_clients=i,
                num_of_client_epochs=2 + i,
                batch_size=16 + i * 8,
                show_plots=True,
                save_plots=False,
            )
            simulation.strategy_config = config

            strategy_history = Mock(spec=SimulationStrategyHistory)

            client_info = Mock(spec=ClientInfo)
            client_info.rounds = [1, 2, 3]
            strategy_history.get_all_clients.return_value = [client_info]

            rounds_history = Mock(spec=RoundsInfo)
            rounds_history.plottable_metrics = ["accuracy", "loss"]
            rounds_history.barable_metrics = ["num_clients"]
            rounds_history.get_metric_by_name.side_effect = lambda metric: (
                [0.7 + i * 0.1, 0.8 + i * 0.1, 0.9 + i * 0.1]
                if metric in ["accuracy", "loss", "num_clients"]
                else []
            )

            strategy_history.rounds_history = rounds_history
            simulation.strategy_history = strategy_history
            strategies.append(simulation)

        return strategies

    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.savefig")
    def test_show_inter_strategy_plots_line_plots(
        self,
        mock_savefig,
        mock_show,
        mock_figure,
        mock_multiple_strategies,
        mock_directory_handler,
    ):
        """Verifies line plots are created for plottable metrics."""
        show_inter_strategy_plots(mock_multiple_strategies, mock_directory_handler)

        assert mock_figure.call_count >= 2
        mock_show.assert_called()

    @patch("matplotlib.pyplot.tight_layout")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.bar")
    def test_show_inter_strategy_plots_bar_plots(
        self,
        mock_bar,
        mock_figure,
        mock_show,
        mock_tight_layout,
        mock_multiple_strategies,
        mock_directory_handler,
    ):
        """Verifies bar plots are created for barable metrics."""
        show_inter_strategy_plots(mock_multiple_strategies, mock_directory_handler)

        mock_bar.assert_called()

    def test_show_inter_strategy_plots_returns_early_when_plots_disabled(
        self, mock_multiple_strategies, mock_directory_handler
    ):
        """Verifies no figures are created when plots are disabled."""
        mock_multiple_strategies[0].strategy_config.show_plots = False
        mock_multiple_strategies[0].strategy_config.save_plots = False

        with patch("matplotlib.pyplot.figure") as mock_figure:
            show_inter_strategy_plots(mock_multiple_strategies, mock_directory_handler)
            mock_figure.assert_not_called()

    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.savefig")
    def test_show_inter_strategy_plots_saves_when_enabled(
        self,
        mock_savefig,
        mock_figure,
        mock_multiple_strategies,
        mock_directory_handler,
    ):
        """Verifies plots are saved when save_plots is enabled."""
        mock_multiple_strategies[0].strategy_config.save_plots = True
        mock_multiple_strategies[0].strategy_config.show_plots = False

        show_inter_strategy_plots(mock_multiple_strategies, mock_directory_handler)

        mock_savefig.assert_called()

    @patch("matplotlib.pyplot.tight_layout")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.plot")
    def test_show_inter_strategy_plots_handles_empty_metrics(
        self,
        mock_plot,
        mock_figure,
        mock_show,
        mock_tight_layout,
        mock_multiple_strategies,
        mock_directory_handler,
    ):
        """Verifies strategies with empty metrics do not raise exceptions."""
        mock_multiple_strategies[
            0
        ].strategy_history.rounds_history.get_metric_by_name.return_value = []

        show_inter_strategy_plots(mock_multiple_strategies, mock_directory_handler)

        mock_figure.assert_called()

    @patch("matplotlib.pyplot.tight_layout")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.legend")
    def test_show_inter_strategy_plots_legend_handling(
        self,
        mock_legend,
        mock_figure,
        mock_show,
        mock_tight_layout,
        mock_multiple_strategies,
        mock_directory_handler,
    ):
        """Verifies legend is displayed when handles and labels exist."""
        with patch("matplotlib.pyplot.gca") as mock_gca:
            mock_ax = Mock()
            mock_ax.get_legend_handles_labels.return_value = (["handle1"], ["label1"])
            mock_gca.return_value = mock_ax

            show_inter_strategy_plots(mock_multiple_strategies, mock_directory_handler)

            mock_legend.assert_called()

    @patch("matplotlib.pyplot.tight_layout")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.figure")
    def test_show_inter_strategy_plots_no_legend_when_empty(
        self,
        mock_figure,
        mock_show,
        mock_tight_layout,
        mock_multiple_strategies,
        mock_directory_handler,
    ):
        """Verifies legend is skipped when no handles or labels exist."""
        with patch("matplotlib.pyplot.gca") as mock_gca:
            with patch("matplotlib.pyplot.legend") as mock_legend:
                mock_ax = Mock()
                mock_ax.get_legend_handles_labels.return_value = ([], [])
                mock_gca.return_value = mock_ax

                show_inter_strategy_plots(mock_multiple_strategies, mock_directory_handler)

                mock_legend.assert_not_called()

    @patch("matplotlib.pyplot.tight_layout")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.plot")
    def test_show_plots_within_strategy_with_removal_threshold(
        self,
        mock_plot,
        mock_figure,
        mock_show,
        mock_tight_layout,
        mock_simulation_strategy,
        mock_directory_handler,
    ):
        """Verifies removal threshold history is plotted when available."""
        mock_simulation_strategy.strategy_history.rounds_history.removal_threshold_history = [
            0.5,
            0.6,
            0.7,
        ]

        mock_client = mock_simulation_strategy.strategy_history.get_all_clients()[0]
        mock_client.plottable_metrics = ["removal_criterion_history"]
        mock_client.get_metric_by_name = Mock(return_value=[0.4, 0.5, 0.8])
        mock_client.rounds = [1, 2, 3]
        mock_client.aggregation_participation_history = [1, 1, 0]

        show_plots_within_strategy(mock_simulation_strategy, mock_directory_handler)

        assert mock_plot.call_count >= 2

    @patch("matplotlib.pyplot.tight_layout")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.plot")
    def test_show_plots_within_strategy_no_removal_threshold(
        self,
        mock_plot,
        mock_figure,
        mock_show,
        mock_tight_layout,
        mock_simulation_strategy,
        mock_directory_handler,
    ):
        """Verifies plotting works when removal threshold history is empty."""
        mock_simulation_strategy.strategy_history.rounds_history.removal_threshold_history = []

        mock_client = mock_simulation_strategy.strategy_history.get_all_clients()[0]
        mock_client.plottable_metrics = ["removal_criterion_history"]
        mock_client.get_metric_by_name = Mock(return_value=[0.4, 0.5, 0.8])
        mock_client.rounds = [1, 2, 3]
        mock_client.aggregation_participation_history = [1, 1, 0]

        show_plots_within_strategy(mock_simulation_strategy, mock_directory_handler)

        mock_plot.assert_called()

    @patch("matplotlib.pyplot.tight_layout")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.plot")
    def test_show_plots_within_strategy_mismatched_dimensions(
        self,
        mock_plot,
        mock_figure,
        mock_show,
        mock_tight_layout,
        mock_simulation_strategy,
        mock_directory_handler,
    ):
        """Verifies mismatched data dimensions do not raise exceptions."""
        mock_client = mock_simulation_strategy.strategy_history.get_all_clients()[0]

        mock_client.rounds = [1, 2, 3, 4, 5]
        mock_client.accuracy_history = [0.4, 0.5, 0.8]
        mock_client.aggregation_participation_history = [1, 1, 0]
        mock_client.plottable_metrics = ["accuracy_history"]

        show_plots_within_strategy(mock_simulation_strategy, mock_directory_handler)

        mock_plot.assert_called()

    @patch("matplotlib.pyplot.tight_layout")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.plot")
    def test_show_plots_within_strategy_malicious_client_labeling(
        self,
        mock_plot,
        mock_figure,
        mock_show,
        mock_tight_layout,
        mock_simulation_strategy,
        mock_directory_handler,
    ):
        """Verifies malicious clients are labeled in plot legends."""
        mock_client = mock_simulation_strategy.strategy_history.get_all_clients()[0]
        mock_client.is_malicious = True
        mock_client.client_id = 5
        mock_client.plottable_metrics = ["accuracy_history"]
        mock_client.accuracy_history = [0.4, 0.5, 0.8]
        mock_client.rounds = [1, 2, 3]
        mock_client.aggregation_participation_history = [1, 1, 0]

        with patch("matplotlib.pyplot.legend"):
            show_plots_within_strategy(mock_simulation_strategy, mock_directory_handler)

        call_args = [call[1] for call in mock_plot.call_args_list if "label" in call[1]]
        client_labels = [args["label"] for args in call_args if "client_5" in args["label"]]
        assert len(client_labels) > 0

    @patch("matplotlib.pyplot.tight_layout")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.plot")
    def test_show_plots_within_strategy_excluded_values_plotting(
        self,
        mock_plot,
        mock_figure,
        mock_show,
        mock_tight_layout,
        mock_simulation_strategy,
        mock_directory_handler,
    ):
        """Verifies excluded values are plotted with X markers."""
        mock_client = mock_simulation_strategy.strategy_history.get_all_clients()[0]
        mock_client.plottable_metrics = ["accuracy_history"]
        mock_client.accuracy_history = [0.4, 0.5, 0.8]
        mock_client.rounds = [1, 2, 3]
        mock_client.aggregation_participation_history = [
            1,
            0,
            1,
        ]

        show_plots_within_strategy(mock_simulation_strategy, mock_directory_handler)

        x_marker_calls = [
            call for call in mock_plot.call_args_list if len(call[0]) >= 3 and "kx" in call[0]
        ]
        assert len(x_marker_calls) > 0

    @patch("matplotlib.pyplot.tight_layout")
    @patch("matplotlib.pyplot.show")
    def test_show_plots_within_strategy_directory_handler_usage(
        self,
        mock_show,
        mock_tight_layout,
        mock_simulation_strategy,
        mock_directory_handler,
    ):
        """Verifies plots are saved to directory handler's path."""
        mock_simulation_strategy.strategy_config.save_plots = True
        mock_simulation_strategy.strategy_config.show_plots = False

        with patch("matplotlib.pyplot.savefig") as mock_savefig:
            with patch("matplotlib.pyplot.figure"):
                show_plots_within_strategy(mock_simulation_strategy, mock_directory_handler)

        save_calls = [call[0][0] for call in mock_savefig.call_args_list]
        assert any(mock_directory_handler.new_plots_dirname in path for path in save_calls)

    @patch("matplotlib.pyplot.tight_layout")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.figure")
    def test_show_inter_strategy_plots_bar_chart_positioning(
        self,
        mock_figure,
        mock_show,
        mock_tight_layout,
        mock_multiple_strategies,
        mock_directory_handler,
    ):
        """Verifies bar charts have correct x-axis positions."""
        with patch("matplotlib.pyplot.bar") as mock_bar:
            with patch("numpy.arange") as mock_arange:
                mock_arange.return_value = np.array([0, 1, 2])

                show_inter_strategy_plots(mock_multiple_strategies, mock_directory_handler)

                bar_calls = mock_bar.call_args_list
                if bar_calls:
                    x_positions = [call[0][0] for call in bar_calls]
                    assert len(x_positions) > 0

    @patch("matplotlib.pyplot.tight_layout")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.gca")
    @patch("matplotlib.pyplot.figure")
    def test_show_plots_within_strategy_axis_configuration(
        self,
        mock_figure,
        mock_gca,
        mock_show,
        mock_tight_layout,
        mock_simulation_strategy,
        mock_directory_handler,
    ):
        """Verifies x-axis major locator is configured."""
        mock_ax = Mock()
        mock_gca.return_value = mock_ax

        show_plots_within_strategy(mock_simulation_strategy, mock_directory_handler)

        mock_ax.xaxis.set_major_locator.assert_called()

    @patch("matplotlib.pyplot.tight_layout")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.gca")
    @patch("matplotlib.pyplot.figure")
    def test_show_inter_strategy_plots_axis_configuration(
        self,
        mock_figure,
        mock_gca,
        mock_show,
        mock_tight_layout,
        mock_multiple_strategies,
        mock_directory_handler,
    ):
        """Verifies bar chart x-axis ticks and labels are configured."""
        mock_ax = Mock()
        mock_ax.get_legend_handles_labels.return_value = ([], [])
        mock_gca.return_value = mock_ax

        show_inter_strategy_plots(mock_multiple_strategies, mock_directory_handler)

        mock_ax.set_xticks.assert_called()
        mock_ax.set_xticklabels.assert_called()

    @patch("matplotlib.pyplot.tight_layout")
    @patch("matplotlib.pyplot.show")
    @patch("math.ceil")
    @patch("matplotlib.pyplot.legend")
    @patch("matplotlib.pyplot.figure")
    def test_show_plots_within_strategy_legend_columns(
        self,
        mock_figure,
        mock_legend,
        mock_ceil,
        mock_show,
        mock_tight_layout,
        mock_simulation_strategy,
        mock_directory_handler,
    ):
        """Verifies legend column count is calculated using math.ceil."""
        mock_ceil.return_value = 3

        show_plots_within_strategy(mock_simulation_strategy, mock_directory_handler)

        mock_ceil.assert_called()
        legend_calls = [call for call in mock_legend.call_args_list if "ncol" in call[1]]
        assert len(legend_calls) > 0

    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.figure")
    def test_show_plots_within_strategy_layout_adjustment(
        self,
        mock_figure,
        mock_show,
        mock_simulation_strategy,
        mock_directory_handler,
    ):
        """Verifies constrained layout is used for plots."""
        show_plots_within_strategy(mock_simulation_strategy, mock_directory_handler)

        mock_figure.assert_called()
        call_kwargs = mock_figure.call_args_list[0].kwargs
        assert call_kwargs.get("layout") == "constrained"

    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.figure")
    def test_show_inter_strategy_plots_layout_adjustment(
        self,
        mock_figure,
        mock_show,
        mock_multiple_strategies,
        mock_directory_handler,
    ):
        """Verifies constrained layout is used for inter-strategy plots."""
        show_inter_strategy_plots(mock_multiple_strategies, mock_directory_handler)

        mock_figure.assert_called()
        call_kwargs = mock_figure.call_args_list[0].kwargs
        assert call_kwargs.get("layout") == "constrained"

    def test_plot_configuration_constants_access(self):
        """Verifies plot_size and bar_width constants have expected types."""
        assert isinstance(plot_size, tuple)
        assert len(plot_size) == 2
        assert isinstance(bar_width, (int, float))
        assert bar_width > 0


class TestGetClientAttackSummary:
    """Tests for _get_client_attack_summary function."""

    def test_empty_attack_schedule_returns_empty_string(self):
        """Returns empty string when no attack schedule provided."""
        result = _get_client_attack_summary(client_id=0, attack_schedule=[])
        assert result == ""

    def test_none_attack_schedule_returns_empty_string(self):
        """Returns empty string when attack schedule is None."""
        # Test defensive behavior - code handles None even if not typed
        result = _get_client_attack_summary(client_id=0, attack_schedule=None)  # type: ignore[arg-type]
        assert result == ""

    def test_specific_selection_targeted_client(self):
        """Returns attack summary for specifically targeted client."""
        schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [0, 2],
                "attack_type": "label_flipping",
                "start_round": 2,
                "end_round": 6,
            }
        ]
        result = _get_client_attack_summary(client_id=0, attack_schedule=schedule)
        assert result == " (lf r2-6)"

    def test_specific_selection_non_targeted_client(self):
        """Returns empty string for client not specifically targeted."""
        schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [1, 3],
                "attack_type": "label_flipping",
                "start_round": 2,
                "end_round": 6,
            }
        ]
        result = _get_client_attack_summary(client_id=0, attack_schedule=schedule)
        assert result == ""

    def test_random_selection_with_selected_clients(self):
        """Returns attack summary for randomly selected client."""
        schedule = [
            {
                "selection_strategy": "random",
                "_selected_clients": [0, 4],
                "attack_type": "gaussian_noise",
                "start_round": 3,
                "end_round": 8,
            }
        ]
        result = _get_client_attack_summary(client_id=0, attack_schedule=schedule)
        assert result == " (gn r3-8)"

    def test_percentage_selection_with_selected_clients(self):
        """Returns attack summary for percentage-selected client."""
        schedule = [
            {
                "selection_strategy": "percentage",
                "_selected_clients": [2, 5],
                "attack_type": "token_replacement",
                "start_round": 1,
                "end_round": 4,
            }
        ]
        result = _get_client_attack_summary(client_id=2, attack_schedule=schedule)
        assert result == " (tr r1-4)"

    def test_multiple_attacks_on_single_client(self):
        """Returns comma-separated summary for multiple attacks."""
        schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
                "attack_type": "label_flipping",
                "start_round": 2,
                "end_round": 5,
            },
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
                "attack_type": "gaussian_noise",
                "start_round": 6,
                "end_round": 10,
            },
        ]
        result = _get_client_attack_summary(client_id=0, attack_schedule=schedule)
        assert result == " (lf r2-5, gn r6-10)"

    def test_unknown_attack_type_uses_first_two_chars(self):
        """Unknown attack types are abbreviated to first 2 characters."""
        schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
                "attack_type": "custom_attack",
                "start_round": 1,
                "end_round": 3,
            }
        ]
        result = _get_client_attack_summary(client_id=0, attack_schedule=schedule)
        assert result == " (cu r1-3)"

    def test_attack_abbrev_constant(self):
        """Verifies ATTACK_ABBREV contains expected mappings."""
        assert ATTACK_ABBREV["label_flipping"] == "lf"
        assert ATTACK_ABBREV["gaussian_noise"] == "gn"
        assert ATTACK_ABBREV["token_replacement"] == "tr"


class TestIsClientMalicious:
    """Tests for _is_client_malicious function."""

    def test_empty_attack_schedule_returns_false(self):
        """Returns False when no attack schedule provided."""
        result = _is_client_malicious(client_id=0, attack_schedule=[])
        assert result is False

    def test_none_attack_schedule_returns_false(self):
        """Returns False when attack schedule is None."""
        # Test defensive behavior - code handles None even if not typed
        result = _is_client_malicious(client_id=0, attack_schedule=None)  # type: ignore[arg-type]
        assert result is False

    def test_specific_selection_targeted_returns_true(self):
        """Returns True for specifically targeted client."""
        schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [0, 2],
                "attack_type": "label_flipping",
                "start_round": 1,
                "end_round": 5,
            }
        ]
        assert _is_client_malicious(client_id=0, attack_schedule=schedule) is True
        assert _is_client_malicious(client_id=2, attack_schedule=schedule) is True

    def test_specific_selection_non_targeted_returns_false(self):
        """Returns False for client not specifically targeted."""
        schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [1, 3],
                "attack_type": "label_flipping",
                "start_round": 1,
                "end_round": 5,
            }
        ]
        assert _is_client_malicious(client_id=0, attack_schedule=schedule) is False

    def test_random_selection_with_selected_clients(self):
        """Returns True for randomly selected client."""
        schedule = [
            {
                "selection_strategy": "random",
                "_selected_clients": [0, 4],
                "attack_type": "gaussian_noise",
                "start_round": 2,
                "end_round": 8,
            }
        ]
        assert _is_client_malicious(client_id=0, attack_schedule=schedule) is True
        assert _is_client_malicious(client_id=4, attack_schedule=schedule) is True
        assert _is_client_malicious(client_id=1, attack_schedule=schedule) is False

    def test_percentage_selection_with_selected_clients(self):
        """Returns True for percentage-selected client."""
        schedule = [
            {
                "selection_strategy": "percentage",
                "_selected_clients": [2, 5],
                "attack_type": "token_replacement",
                "start_round": 1,
                "end_round": 4,
            }
        ]
        assert _is_client_malicious(client_id=2, attack_schedule=schedule) is True
        assert _is_client_malicious(client_id=5, attack_schedule=schedule) is True
        assert _is_client_malicious(client_id=0, attack_schedule=schedule) is False

    def test_multiple_attack_entries_any_match(self):
        """Returns True if client is targeted by any attack entry."""
        schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [1],
                "attack_type": "label_flipping",
                "start_round": 1,
                "end_round": 3,
            },
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
                "attack_type": "gaussian_noise",
                "start_round": 4,
                "end_round": 6,
            },
        ]
        assert _is_client_malicious(client_id=0, attack_schedule=schedule) is True

    def test_missing_selection_strategy_returns_false(self):
        """Returns False when selection_strategy is missing."""
        schedule = [
            {
                "malicious_client_ids": [0],
                "attack_type": "label_flipping",
                "start_round": 1,
                "end_round": 3,
            }
        ]
        assert _is_client_malicious(client_id=0, attack_schedule=schedule) is False


class TestAddAttackBackgroundShading:
    """Tests for _add_attack_background_shading function."""

    @pytest.fixture
    def mock_axes(self):
        """Returns a mock Matplotlib axes object."""
        ax = Mock()
        return ax

    def test_empty_attack_schedule_no_shading(self, mock_axes):
        """No shading added when attack schedule is empty."""
        _add_attack_background_shading(mock_axes, attack_schedule=[])
        mock_axes.axvspan.assert_not_called()

    def test_none_attack_schedule_no_shading(self, mock_axes):
        """No shading added when attack schedule is None."""
        # Test defensive behavior - code handles None even if not typed
        _add_attack_background_shading(mock_axes, attack_schedule=None)  # type: ignore[arg-type]
        mock_axes.axvspan.assert_not_called()

    def test_shading_for_label_flipping_attack(self, mock_axes):
        """Adds red shading for label_flipping attacks."""
        schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
                "attack_type": "label_flipping",
                "start_round": 2,
                "end_round": 6,
            }
        ]
        _add_attack_background_shading(mock_axes, schedule)
        mock_axes.axvspan.assert_called_once()
        call_kwargs = mock_axes.axvspan.call_args[1]
        assert call_kwargs["facecolor"] == "#ff9999"  # Red for label_flipping
        assert call_kwargs["hatch"] == "////"

    def test_shading_for_gaussian_noise_attack(self, mock_axes):
        """Adds blue shading for gaussian_noise attacks."""
        schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
                "attack_type": "gaussian_noise",
                "start_round": 3,
                "end_round": 7,
            }
        ]
        _add_attack_background_shading(mock_axes, schedule)
        mock_axes.axvspan.assert_called_once()
        call_kwargs = mock_axes.axvspan.call_args[1]
        assert call_kwargs["facecolor"] == "#9999ff"  # Blue for gaussian_noise
        assert call_kwargs["hatch"] == "\\\\\\\\"

    def test_shading_for_token_replacement_attack(self, mock_axes):
        """Adds green shading for token_replacement attacks."""
        schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
                "attack_type": "token_replacement",
                "start_round": 1,
                "end_round": 4,
            }
        ]
        _add_attack_background_shading(mock_axes, schedule)
        mock_axes.axvspan.assert_called_once()
        call_kwargs = mock_axes.axvspan.call_args[1]
        assert call_kwargs["facecolor"] == "#99ff99"  # Green for token_replacement
        assert call_kwargs["hatch"] == "xxxx"

    def test_unknown_attack_type_uses_default_color(self, mock_axes):
        """Unknown attack types use default gray color."""
        schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
                "attack_type": "custom_attack",
                "start_round": 1,
                "end_round": 3,
            }
        ]
        _add_attack_background_shading(mock_axes, schedule)
        call_kwargs = mock_axes.axvspan.call_args[1]
        assert call_kwargs["facecolor"] == "#dddddd"  # Default gray
        assert call_kwargs["hatch"] == ""

    def test_shading_with_specific_client_id_filter(self, mock_axes):
        """Only shades attacks targeting the specified client."""
        schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
                "attack_type": "label_flipping",
                "start_round": 2,
                "end_round": 6,
            },
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [1],
                "attack_type": "gaussian_noise",
                "start_round": 3,
                "end_round": 7,
            },
        ]
        _add_attack_background_shading(mock_axes, schedule, client_id=0)
        # Only label_flipping should be shaded (client 0)
        assert mock_axes.axvspan.call_count == 1
        call_kwargs = mock_axes.axvspan.call_args[1]
        assert call_kwargs["facecolor"] == "#ff9999"

    def test_shading_with_no_client_id_shows_all_attacks(self, mock_axes):
        """Shows all attacks when client_id is None."""
        schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
                "attack_type": "label_flipping",
                "start_round": 2,
                "end_round": 6,
            },
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [1],
                "attack_type": "gaussian_noise",
                "start_round": 3,
                "end_round": 7,
            },
        ]
        # client_id=None is the default; tests show-all behavior
        _add_attack_background_shading(mock_axes, schedule, client_id=None)  # type: ignore[arg-type]
        assert mock_axes.axvspan.call_count == 2

    def test_duplicate_attack_periods_not_repeated(self, mock_axes):
        """Duplicate attack periods are only added once."""
        schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
                "attack_type": "label_flipping",
                "start_round": 2,
                "end_round": 6,
            },
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [1],
                "attack_type": "label_flipping",
                "start_round": 2,
                "end_round": 6,
            },
        ]
        # client_id=None is the default; shows all attacks
        _add_attack_background_shading(mock_axes, schedule, client_id=None)  # type: ignore[arg-type]
        # Should only add shading once despite two entries with same period
        assert mock_axes.axvspan.call_count == 1

    def test_random_selection_shows_for_all_clients(self, mock_axes):
        """Random selection shows shading for any client."""
        schedule = [
            {
                "selection_strategy": "random",
                "_selected_clients": [2, 5],
                "attack_type": "gaussian_noise",
                "start_round": 3,
                "end_round": 8,
            }
        ]
        # Client 0 should still see the shading for random selection
        _add_attack_background_shading(mock_axes, schedule, client_id=0)
        assert mock_axes.axvspan.call_count == 1

    def test_axvspan_called_with_correct_round_range(self, mock_axes):
        """Verifies axvspan is called with correct start and end rounds."""
        schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
                "attack_type": "label_flipping",
                "start_round": 5,
                "end_round": 10,
            }
        ]
        _add_attack_background_shading(mock_axes, schedule)
        call_args = mock_axes.axvspan.call_args[0]
        assert call_args[0] == 4.6  # start_round - 0.4
        assert call_args[1] == 10.4  # end_round + 0.4


class TestSavePlotDataJson:
    """Tests for save_plot_data_json function."""

    @pytest.fixture
    def mock_client_info_with_metrics(self):
        """Returns mock ClientInfo with plottable metrics."""
        client = Mock(spec=ClientInfo)
        client.client_id = 0
        client.rounds = [1, 2, 3]
        client.plottable_metrics = ["loss_history", "accuracy_history"]
        client.get_metric_by_name = Mock(
            side_effect=lambda name: [0.5, 0.4, 0.3] if name == "loss_history" else [0.7, 0.8, 0.9]
        )
        return client

    @pytest.fixture
    def mock_simulation_for_json(self, mock_client_info_with_metrics, tmp_path):
        """Returns mock FederatedSimulation for JSON export tests."""
        simulation = Mock(spec=FederatedSimulation)

        config = Mock(spec=StrategyConfig)
        config.attack_schedule = []
        config.strategy_number = 0
        simulation.strategy_config = config

        strategy_history = Mock(spec=SimulationStrategyHistory)
        strategy_history.get_all_clients.return_value = [mock_client_info_with_metrics]

        rounds_history = Mock(spec=RoundsInfo)
        rounds_history.removal_threshold_history = []
        rounds_history.average_accuracy_history = []
        rounds_history.aggregated_loss_history = []
        rounds_history.average_accuracy_std_history = []
        strategy_history.rounds_history = rounds_history

        simulation.strategy_history = strategy_history

        return simulation

    @pytest.fixture
    def mock_directory_handler_for_json(self, tmp_path):
        """Returns mock directory handler for JSON tests."""
        handler = Mock()
        handler.dirname = str(tmp_path)
        handler.new_plots_dirname = str(tmp_path)
        return handler

    def test_json_export_creates_file(
        self, mock_simulation_for_json, mock_directory_handler_for_json, tmp_path
    ):
        """Verifies JSON file is created."""
        save_plot_data_json(mock_simulation_for_json, mock_directory_handler_for_json)

        expected_path = tmp_path / "plot_data_0.json"
        assert expected_path.exists()

    def test_json_export_structure(
        self, mock_simulation_for_json, mock_directory_handler_for_json, tmp_path
    ):
        """Verifies exported JSON has correct structure."""
        save_plot_data_json(mock_simulation_for_json, mock_directory_handler_for_json)

        with open(tmp_path / "plot_data_0.json") as f:
            data = json.load(f)

        assert "per_client_metrics" in data
        assert "rounds" in data
        assert "removal_threshold_history" in data
        assert "strategy_number" in data

    def test_json_export_per_client_metrics(
        self, mock_simulation_for_json, mock_directory_handler_for_json, tmp_path
    ):
        """Verifies per-client metrics are correctly exported."""
        save_plot_data_json(mock_simulation_for_json, mock_directory_handler_for_json)

        with open(tmp_path / "plot_data_0.json") as f:
            data = json.load(f)

        client_data = data["per_client_metrics"][0]
        assert client_data["client_id"] == 0
        assert "is_malicious" in client_data
        assert "metrics" in client_data
        assert "loss_history" in client_data["metrics"]
        assert "accuracy_history" in client_data["metrics"]

    def test_json_export_rounds(
        self, mock_simulation_for_json, mock_directory_handler_for_json, tmp_path
    ):
        """Verifies rounds are correctly exported."""
        save_plot_data_json(mock_simulation_for_json, mock_directory_handler_for_json)

        with open(tmp_path / "plot_data_0.json") as f:
            data = json.load(f)

        assert data["rounds"] == [1, 2, 3]

    def test_json_export_with_attack_schedule(
        self, mock_simulation_for_json, mock_directory_handler_for_json, tmp_path
    ):
        """Verifies malicious flag is set correctly with attacks."""
        mock_simulation_for_json.strategy_config.attack_schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
                "attack_type": "label_flipping",
                "start_round": 1,
                "end_round": 3,
            }
        ]

        save_plot_data_json(mock_simulation_for_json, mock_directory_handler_for_json)

        with open(tmp_path / "plot_data_0.json") as f:
            data = json.load(f)

        assert data["per_client_metrics"][0]["is_malicious"] is True

    def test_json_export_with_removal_threshold(
        self, mock_simulation_for_json, mock_directory_handler_for_json, tmp_path
    ):
        """Verifies removal threshold history is exported."""
        mock_simulation_for_json.strategy_history.rounds_history.removal_threshold_history = [
            0.5,
            0.6,
            0.7,
        ]

        save_plot_data_json(mock_simulation_for_json, mock_directory_handler_for_json)

        with open(tmp_path / "plot_data_0.json") as f:
            data = json.load(f)

        assert data["removal_threshold_history"] == [0.5, 0.6, 0.7]

    def test_json_export_empty_clients_returns_early(
        self, mock_simulation_for_json, mock_directory_handler_for_json, tmp_path
    ):
        """Verifies early return when no clients."""
        mock_simulation_for_json.strategy_history.get_all_clients.return_value = []

        save_plot_data_json(mock_simulation_for_json, mock_directory_handler_for_json)

        # No file should be created
        json_files = list(tmp_path.glob("*.json"))
        assert len(json_files) == 0

    def test_json_export_handles_none_metric_values(
        self, mock_simulation_for_json, mock_directory_handler_for_json, tmp_path
    ):
        """Verifies None values in metrics are exported as null."""
        mock_client = mock_simulation_for_json.strategy_history.get_all_clients.return_value[0]
        mock_client.get_metric_by_name = Mock(return_value=[0.5, None, 0.7])

        save_plot_data_json(mock_simulation_for_json, mock_directory_handler_for_json)

        with open(tmp_path / "plot_data_0.json") as f:
            data = json.load(f)

        metrics = data["per_client_metrics"][0]["metrics"]["loss_history"]
        assert metrics[0] == 0.5
        assert metrics[1] is None
        assert metrics[2] == 0.7

    def test_json_export_strategy_number(
        self, mock_simulation_for_json, mock_directory_handler_for_json, tmp_path
    ):
        """Verifies strategy number is included in export."""
        mock_simulation_for_json.strategy_config.strategy_number = 5

        save_plot_data_json(mock_simulation_for_json, mock_directory_handler_for_json)

        expected_path = tmp_path / "plot_data_5.json"
        assert expected_path.exists()

        with open(expected_path) as f:
            data = json.load(f)

        assert data["strategy_number"] == 5

    def test_json_export_multiple_clients(self, mock_directory_handler_for_json, tmp_path):
        """Verifies multiple clients are correctly exported."""
        # Create multiple client mocks
        clients = []
        for i in range(3):
            client = Mock(spec=ClientInfo)
            client.client_id = i
            client.rounds = [1, 2, 3]
            client.plottable_metrics = ["loss_history"]
            client.get_metric_by_name = Mock(return_value=[0.5 - i * 0.1, 0.4, 0.3])
            clients.append(client)

        simulation = Mock(spec=FederatedSimulation)
        config = Mock(spec=StrategyConfig)
        config.attack_schedule = []
        config.strategy_number = 0
        simulation.strategy_config = config

        strategy_history = Mock(spec=SimulationStrategyHistory)
        strategy_history.get_all_clients.return_value = clients
        rounds_history = Mock(spec=RoundsInfo)
        rounds_history.removal_threshold_history = []
        rounds_history.average_accuracy_history = []
        rounds_history.aggregated_loss_history = []
        rounds_history.average_accuracy_std_history = []
        strategy_history.rounds_history = rounds_history
        simulation.strategy_history = strategy_history

        save_plot_data_json(simulation, mock_directory_handler_for_json)

        with open(tmp_path / "plot_data_0.json") as f:
            data = json.load(f)

        assert len(data["per_client_metrics"]) == 3
        for i, client_data in enumerate(data["per_client_metrics"]):
            assert client_data["client_id"] == i


class TestShowPlotsWithAttackShading:
    """Tests for attack shading integration in show_plots_within_strategy."""

    @pytest.fixture
    def simulation_with_attacks(self, tmp_path):
        """Returns mock simulation with attack schedule."""
        simulation = Mock(spec=FederatedSimulation)

        config = StrategyConfig(
            aggregation_strategy_keyword="fedavg",
            dataset_keyword="femnist",
            remove_clients=False,
            num_of_clients=5,
            num_of_malicious_clients=1,
            num_of_client_epochs=2,
            batch_size=32,
            show_plots=True,
            save_plots=False,
        )
        config.attack_schedule = [
            {
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
                "attack_type": "label_flipping",
                "start_round": 2,
                "end_round": 5,
            }
        ]
        simulation.strategy_config = config

        client = Mock(spec=ClientInfo)
        client.client_id = 0
        client.rounds = [1, 2, 3, 4, 5]
        client.plottable_metrics = ["loss_history"]
        client.loss_history = [0.5, 0.4, 0.3, 0.25, 0.2]
        client.get_metric_by_name = Mock(return_value=[0.5, 0.4, 0.3, 0.25, 0.2])
        client.aggregation_participation_history = [1, 1, 1, 1, 1]

        strategy_history = Mock(spec=SimulationStrategyHistory)
        strategy_history.get_all_clients.return_value = [client]
        rounds_history = Mock(spec=RoundsInfo)
        rounds_history.removal_threshold_history = []
        rounds_history.average_accuracy_history = []
        rounds_history.aggregated_loss_history = []
        rounds_history.average_accuracy_std_history = []
        strategy_history.rounds_history = rounds_history
        simulation.strategy_history = strategy_history

        return simulation

    @pytest.fixture
    def dir_handler(self, tmp_path):
        """Returns mock directory handler."""
        handler = Mock()
        handler.dirname = str(tmp_path)
        handler.new_plots_dirname = str(tmp_path)
        return handler

    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.gca")
    def test_attack_shading_called_with_schedule(
        self,
        mock_gca,
        mock_show,
        mock_figure,
        simulation_with_attacks,
        dir_handler,
    ):
        """Verifies attack shading is applied when schedule exists."""
        mock_ax = Mock()
        mock_ax.xaxis = Mock()
        mock_ax.xaxis.set_major_locator = Mock()
        mock_gca.return_value = mock_ax

        show_plots_within_strategy(simulation_with_attacks, dir_handler)

        # Verify axvspan was called for attack shading
        assert mock_ax.axvspan.called

    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.gca")
    def test_no_attack_shading_without_schedule(
        self,
        mock_gca,
        mock_show,
        mock_figure,
        simulation_with_attacks,
        dir_handler,
    ):
        """Verifies no shading when attack schedule is empty."""
        simulation_with_attacks.strategy_config.attack_schedule = []

        mock_ax = Mock()
        mock_ax.xaxis = Mock()
        mock_ax.xaxis.set_major_locator = Mock()
        mock_gca.return_value = mock_ax

        show_plots_within_strategy(simulation_with_attacks, dir_handler)

        # axvspan should not be called
        mock_ax.axvspan.assert_not_called()

    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.savefig")
    @patch("matplotlib.pyplot.gca")
    def test_inter_strategy_attack_shading_called_with_schedule(
        self,
        mock_gca,
        mock_savefig,
        mock_show,
        mock_figure,
        simulation_with_attacks,
        dir_handler,
    ):
        """Inter-strategy plots apply the same attack-round shading as per-client plots."""
        mock_ax = Mock()
        mock_ax.xaxis = Mock()
        mock_ax.xaxis.set_major_locator = Mock()
        mock_ax.get_legend_handles_labels.return_value = ([], [])
        mock_gca.return_value = mock_ax

        # `attack_schedule` is sourced from strategies[0].strategy_config, so
        # both members of the list share the same schedule (the comparison
        # axis is the strategy, not the attack).
        simulation_with_attacks.strategy_history.rounds_history.plottable_metrics = [
            "aggregated_loss_history"
        ]
        simulation_with_attacks.strategy_history.rounds_history.barable_metrics = []
        simulation_with_attacks.strategy_history.rounds_history.get_metric_by_name = Mock(
            return_value=[0.5, 0.4, 0.3, 0.25, 0.2]
        )

        show_inter_strategy_plots([simulation_with_attacks], dir_handler)

        # axvspan was called by _add_attack_background_shading
        assert mock_ax.axvspan.called

    @patch("matplotlib.pyplot.figure")
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.savefig")
    @patch("matplotlib.pyplot.gca")
    def test_no_inter_strategy_attack_shading_without_schedule(
        self,
        mock_gca,
        mock_savefig,
        mock_show,
        mock_figure,
        simulation_with_attacks,
        dir_handler,
    ):
        """Inter-strategy plots without an attack schedule render no shading."""
        simulation_with_attacks.strategy_config.attack_schedule = []

        mock_ax = Mock()
        mock_ax.xaxis = Mock()
        mock_ax.xaxis.set_major_locator = Mock()
        mock_ax.get_legend_handles_labels.return_value = ([], [])
        mock_gca.return_value = mock_ax

        simulation_with_attacks.strategy_history.rounds_history.plottable_metrics = [
            "aggregated_loss_history"
        ]
        simulation_with_attacks.strategy_history.rounds_history.barable_metrics = []
        simulation_with_attacks.strategy_history.rounds_history.get_metric_by_name = Mock(
            return_value=[0.5, 0.4, 0.3, 0.25, 0.2]
        )

        show_inter_strategy_plots([simulation_with_attacks], dir_handler)

        mock_ax.axvspan.assert_not_called()
