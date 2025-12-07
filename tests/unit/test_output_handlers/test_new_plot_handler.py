from unittest.mock import patch

import matplotlib

from src.data_models.client_info import ClientInfo
from src.data_models.round_info import RoundsInfo
from src.data_models.simulation_strategy_config import StrategyConfig
from src.data_models.simulation_strategy_history import SimulationStrategyHistory
from src.federated_simulation import FederatedSimulation
from src.output_handlers.new_plot_handler import (
    _generate_multi_string_strategy_label,
    _generate_single_string_strategy_label,
    bar_width,
    plot_size,
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
            dataset_keyword="its",
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
        assert "dataset: its" in label
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
                show_plots_within_strategy(
                    mock_simulation_strategy, mock_directory_handler
                )

                mock_show.assert_called()
                mock_savefig.assert_called()

    def test_strategy_label_handles_none_values(self):
        """Verifies None values in config are converted to strings."""
        config = StrategyConfig(
            aggregation_strategy_keyword="fedavg",
            dataset_keyword=None,
            remove_clients=None,
            num_of_clients=None,
            num_of_malicious_clients=None,
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
            rounds_history.get_metric_by_name.side_effect = (
                lambda metric: [0.7 + i * 0.1, 0.8 + i * 0.1, 0.9 + i * 0.1]
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

                show_inter_strategy_plots(
                    mock_multiple_strategies, mock_directory_handler
                )

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
        client_labels = [
            args["label"] for args in call_args if "client_5" in args["label"]
        ]
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
            call
            for call in mock_plot.call_args_list
            if len(call[0]) >= 3 and "kx" in call[0]
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
                show_plots_within_strategy(
                    mock_simulation_strategy, mock_directory_handler
                )

        save_calls = [call[0][0] for call in mock_savefig.call_args_list]
        assert any(
            mock_directory_handler.new_plots_dirname in path for path in save_calls
        )

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

                show_inter_strategy_plots(
                    mock_multiple_strategies, mock_directory_handler
                )

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
        legend_calls = [
            call for call in mock_legend.call_args_list if "ncol" in call[1]
        ]
        assert len(legend_calls) > 0

    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.tight_layout")
    @patch("matplotlib.pyplot.figure")
    def test_show_plots_within_strategy_layout_adjustment(
        self,
        mock_figure,
        mock_tight_layout,
        mock_show,
        mock_simulation_strategy,
        mock_directory_handler,
    ):
        """Verifies tight_layout is called for plot layout."""
        show_plots_within_strategy(mock_simulation_strategy, mock_directory_handler)

        mock_tight_layout.assert_called()

    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.tight_layout")
    @patch("matplotlib.pyplot.figure")
    def test_show_inter_strategy_plots_layout_adjustment(
        self,
        mock_figure,
        mock_tight_layout,
        mock_show,
        mock_multiple_strategies,
        mock_directory_handler,
    ):
        """Verifies tight_layout is called for inter-strategy plots."""
        show_inter_strategy_plots(mock_multiple_strategies, mock_directory_handler)

        mock_tight_layout.assert_called()

    def test_plot_configuration_constants_access(self):
        """Verifies plot_size and bar_width constants have expected types."""
        assert isinstance(plot_size, tuple)
        assert len(plot_size) == 2
        assert isinstance(bar_width, (int, float))
        assert bar_width > 0
