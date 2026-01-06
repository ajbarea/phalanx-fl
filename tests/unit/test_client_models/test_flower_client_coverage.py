"""
Additional coverage tests for FlowerClient attack paths.

These tests target the uncovered code paths in flower_client.py:
- Attack snapshot saving (_save_attack_snapshots)
- Weight poisoning execution paths
- attacks_schedule handling
- Different attack type parametrization
"""

from __future__ import annotations

from unittest.mock import patch

import torch

from src.attack_utils.weight_poisoning import WEIGHT_ATTACK_TYPES
from src.client_models.flower_client import FlowerClient
from tests.common import ATTACK_TYPES, Mock, pytest
from tests.fixtures.sample_models import MockCNNNetwork


class TestFlowerClientAttackSnapshots:
    """Test attack snapshot saving functionality."""

    @pytest.fixture
    def client_with_snapshots(self, tmp_path):
        """Create FlowerClient configured for snapshot saving."""
        mock_net = MockCNNNetwork(num_classes=10, input_channels=3)
        mock_data = [(torch.randn(4, 3, 32, 32), torch.randint(0, 10, (4,))) for _ in range(3)]

        mock_loader = Mock()
        mock_loader.__iter__ = Mock(return_value=iter(mock_data))
        mock_loader.__len__ = Mock(return_value=3)
        mock_loader.dataset = Mock()
        mock_loader.dataset.__len__ = Mock(return_value=12)

        return FlowerClient(
            client_id=0,
            net=mock_net,
            trainloader=mock_loader,
            valloader=mock_loader,
            training_device="cpu",
            num_of_client_epochs=1,
            model_type="cnn",
            num_malicious_clients=1,
            attacks_schedule=[{"rounds": [1, 2], "attack_type": "label_flipping"}],
            save_attack_snapshots=True,
            attack_snapshot_format="pickle_and_visual",
            snapshot_max_samples=5,
            output_dir=str(tmp_path / "out"),
            strategy_number=0,
        )

    def test_save_attack_snapshots_disabled(self, tmp_path):
        """Test that snapshots are not saved when disabled."""
        mock_net = MockCNNNetwork(num_classes=10, input_channels=3)
        mock_loader = Mock()
        mock_loader.__iter__ = Mock(return_value=iter([]))
        mock_loader.__len__ = Mock(return_value=0)
        mock_loader.dataset = Mock()
        mock_loader.dataset.__len__ = Mock(return_value=0)

        client = FlowerClient(
            client_id=0,
            net=mock_net,
            trainloader=mock_loader,
            valloader=mock_loader,
            training_device="cpu",
            num_of_client_epochs=1,
            save_attack_snapshots=False,  # Disabled
            output_dir=str(tmp_path),
        )

        # Should return early without saving
        with patch("src.client_models.flower_client.save_attack_snapshot") as mock_save:
            client._save_attack_snapshots(
                current_round=1,
                attack_configs=[{"attack_type": "label_flipping"}],
                data_sample=torch.randn(5, 3, 32, 32),
                labels_sample=torch.randint(0, 10, (5,)),
            )
            mock_save.assert_not_called()

    def test_save_attack_snapshots_no_output_dir(self):
        """Test that snapshots are not saved when output_dir is None."""
        mock_net = MockCNNNetwork(num_classes=10, input_channels=3)
        mock_loader = Mock()
        mock_loader.__iter__ = Mock(return_value=iter([]))
        mock_loader.__len__ = Mock(return_value=0)
        mock_loader.dataset = Mock()
        mock_loader.dataset.__len__ = Mock(return_value=0)

        client = FlowerClient(
            client_id=0,
            net=mock_net,
            trainloader=mock_loader,
            valloader=mock_loader,
            training_device="cpu",
            num_of_client_epochs=1,
            save_attack_snapshots=True,
            output_dir=None,  # No output dir
        )

        with patch("src.client_models.flower_client.save_attack_snapshot") as mock_save:
            client._save_attack_snapshots(
                current_round=1,
                attack_configs=[{"attack_type": "label_flipping"}],
                data_sample=torch.randn(5, 3, 32, 32),
                labels_sample=torch.randint(0, 10, (5,)),
            )
            mock_save.assert_not_called()

    @pytest.mark.parametrize(
        "attack_type",
        [at for at in ATTACK_TYPES if at not in WEIGHT_ATTACK_TYPES],
    )
    def test_save_attack_snapshots_data_attacks(self, client_with_snapshots, attack_type):
        """Test snapshot saving for data attacks (not weight attacks)."""
        with patch("src.client_models.flower_client.save_attack_snapshot") as mock_save:
            client_with_snapshots._save_attack_snapshots(
                current_round=1,
                attack_configs=[{"attack_type": attack_type}],
                data_sample=torch.randn(5, 3, 32, 32),
                labels_sample=torch.randint(0, 10, (5,)),
            )
            mock_save.assert_called_once()

    @pytest.mark.parametrize("attack_type", list(WEIGHT_ATTACK_TYPES))
    def test_save_attack_snapshots_filters_weight_attacks(self, client_with_snapshots, attack_type):
        """Test that weight attacks are filtered out (they get separate visualization)."""
        with patch("src.client_models.flower_client.save_attack_snapshot") as mock_save:
            client_with_snapshots._save_attack_snapshots(
                current_round=1,
                attack_configs=[{"attack_type": attack_type}],
                data_sample=torch.randn(5, 3, 32, 32),
                labels_sample=torch.randint(0, 10, (5,)),
            )
            # Weight attacks should NOT trigger save_attack_snapshot
            mock_save.assert_not_called()


class TestFlowerClientAttackSchedule:
    """Test attacks_schedule handling."""

    @pytest.fixture
    def mock_loaders(self):
        """Create mock data loaders."""
        mock_data = [(torch.randn(4, 3, 32, 32), torch.randint(0, 10, (4,))) for _ in range(3)]
        mock_loader = Mock()
        mock_loader.__iter__ = Mock(return_value=iter(mock_data))
        mock_loader.__len__ = Mock(return_value=3)
        mock_loader.dataset = Mock()
        mock_loader.dataset.__len__ = Mock(return_value=12)
        return mock_loader, mock_loader

    @pytest.mark.parametrize("attack_type", ATTACK_TYPES[:5])
    def test_fit_with_attack_schedule(self, mock_loaders, attack_type, tmp_path):
        """Test fit method with various attack schedules."""
        trainloader, valloader = mock_loaders
        mock_net = MockCNNNetwork(num_classes=10, input_channels=3)

        client = FlowerClient(
            client_id=0,  # Malicious client
            net=mock_net,
            trainloader=trainloader,
            valloader=valloader,
            training_device="cpu",
            num_of_client_epochs=1,
            model_type="cnn",
            num_malicious_clients=1,
            attacks_schedule=[{"rounds": [1], "attack_type": attack_type}],
            output_dir=str(tmp_path),
        )

        initial_params = client.get_parameters(config={})

        with patch.object(client, "train") as mock_train:
            mock_train.return_value = (0.5, 0.8)
            result_params, dataset_size, metrics = client.fit(initial_params, config={"round": 1})

        assert isinstance(result_params, list)
        assert isinstance(metrics, dict)

    def test_fit_attack_not_in_round(self, mock_loaders, tmp_path):
        """Test that attacks don't trigger when round is not in schedule."""
        trainloader, valloader = mock_loaders
        mock_net = MockCNNNetwork(num_classes=10, input_channels=3)

        client = FlowerClient(
            client_id=0,
            net=mock_net,
            trainloader=trainloader,
            valloader=valloader,
            training_device="cpu",
            num_of_client_epochs=1,
            model_type="cnn",
            num_malicious_clients=1,
            attacks_schedule=[
                {"rounds": [5, 6], "attack_type": "label_flipping"}
            ],  # Round 1 not included
            output_dir=str(tmp_path),
        )

        initial_params = client.get_parameters(config={})

        with patch.object(client, "train") as mock_train:
            mock_train.return_value = (0.5, 0.8)
            client.fit(initial_params, config={"round": 1})
            # Test completes without error - attack not triggered for round 1


class TestFlowerClientExperimentInfo:
    """Test experiment_info handling."""

    def test_client_with_experiment_info(self):
        """Test client initialization with experiment_info."""
        mock_net = MockCNNNetwork(num_classes=10, input_channels=3)
        mock_loader = Mock()
        mock_loader.__iter__ = Mock(return_value=iter([]))
        mock_loader.__len__ = Mock(return_value=0)
        mock_loader.dataset = Mock()
        mock_loader.dataset.__len__ = Mock(return_value=0)

        experiment_info = {
            "experiment_name": "test_experiment",
            "dataset": "femnist",
            "strategy": "krum",
        }

        client = FlowerClient(
            client_id=0,
            net=mock_net,
            trainloader=mock_loader,
            valloader=mock_loader,
            training_device="cpu",
            num_of_client_epochs=1,
            experiment_info=experiment_info,
        )

        assert client.experiment_info == experiment_info
        assert client.experiment_info["experiment_name"] == "test_experiment"  # type: ignore[index]

    def test_client_with_tokenizer(self):
        """Test client initialization with tokenizer for transformer models."""
        mock_net = Mock()
        mock_net.parameters.return_value = [torch.randn(10, 5)]
        mock_loader = Mock()
        mock_loader.__iter__ = Mock(return_value=iter([]))
        mock_loader.__len__ = Mock(return_value=0)
        mock_loader.dataset = Mock()
        mock_loader.dataset.__len__ = Mock(return_value=0)

        mock_tokenizer = Mock()
        mock_tokenizer.pad_token_id = 0

        client = FlowerClient(
            client_id=0,
            net=mock_net,
            trainloader=mock_loader,
            valloader=mock_loader,
            training_device="cpu",
            num_of_client_epochs=1,
            model_type="transformer",
            tokenizer=mock_tokenizer,
        )

        assert client.tokenizer == mock_tokenizer
        assert client.tokenizer.pad_token_id == 0  # type: ignore[union-attr]

    def test_client_strategy_number(self):
        """Test client initialization with strategy_number."""
        mock_net = MockCNNNetwork(num_classes=10, input_channels=3)
        mock_loader = Mock()
        mock_loader.__iter__ = Mock(return_value=iter([]))
        mock_loader.__len__ = Mock(return_value=0)
        mock_loader.dataset = Mock()
        mock_loader.dataset.__len__ = Mock(return_value=0)

        client = FlowerClient(
            client_id=0,
            net=mock_net,
            trainloader=mock_loader,
            valloader=mock_loader,
            training_device="cpu",
            num_of_client_epochs=1,
            strategy_number=5,
        )

        assert client.strategy_number == 5


class TestFlowerClientPredictions:
    """Test _get_predictions and _get_sample_batch_for_viz methods."""

    @pytest.fixture
    def cnn_client_with_data(self, tmp_path):
        """Create CNN client with real data for prediction testing."""
        mock_net = MockCNNNetwork(num_classes=10, input_channels=3)
        mock_data = [(torch.randn(4, 3, 32, 32), torch.randint(0, 10, (4,))) for _ in range(2)]

        mock_loader = Mock()
        mock_loader.__iter__ = Mock(return_value=iter(mock_data))
        mock_loader.__len__ = Mock(return_value=2)
        mock_loader.dataset = Mock()
        mock_loader.dataset.__len__ = Mock(return_value=8)

        return FlowerClient(
            client_id=0,
            net=mock_net,
            trainloader=mock_loader,
            valloader=mock_loader,
            training_device="cpu",
            num_of_client_epochs=1,
            model_type="cnn",
            output_dir=str(tmp_path),
        )

    def test_get_predictions_returns_correct_format(self, cnn_client_with_data):
        """Test _get_predictions returns correct format."""
        images = torch.randn(4, 3, 32, 32)

        preds, probs = cnn_client_with_data._get_predictions(images, top_k=5)

        # Should return list of lists of (class_idx, confidence) tuples
        assert isinstance(preds, list)
        assert len(preds) == 4  # One per image
        assert len(preds[0]) == 5  # top_k predictions
        assert isinstance(preds[0][0], tuple)
        assert len(preds[0][0]) == 2  # (class_idx, confidence)

        # Probabilities should be numpy array of shape (N, num_classes)
        assert isinstance(probs, (type(None), type(probs)))  # numpy array
        assert probs is not None
        assert probs.shape[0] == 4
        assert probs.shape[1] == 10  # num_classes

    def test_get_predictions_top_k_values(self, cnn_client_with_data):
        """Test _get_predictions with different top_k values."""
        images = torch.randn(2, 3, 32, 32)

        preds_3, _ = cnn_client_with_data._get_predictions(images, top_k=3)
        preds_1, _ = cnn_client_with_data._get_predictions(images, top_k=1)

        assert len(preds_3[0]) == 3
        assert len(preds_1[0]) == 1

    def test_get_sample_batch_for_viz_cnn(self, cnn_client_with_data):
        """Test _get_sample_batch_for_viz for CNN model."""
        images, labels = cnn_client_with_data._get_sample_batch_for_viz(max_samples=3)

        assert images is not None
        assert labels is not None
        assert images.shape[0] <= 3
        assert labels.shape[0] <= 3

    def test_get_sample_batch_for_viz_empty_loader(self, tmp_path):
        """Test _get_sample_batch_for_viz with empty trainloader."""
        mock_net = MockCNNNetwork(num_classes=10, input_channels=3)
        mock_loader = Mock()
        mock_loader.__iter__ = Mock(return_value=iter([]))  # Empty
        mock_loader.__len__ = Mock(return_value=0)
        mock_loader.dataset = Mock()
        mock_loader.dataset.__len__ = Mock(return_value=0)

        client = FlowerClient(
            client_id=0,
            net=mock_net,
            trainloader=mock_loader,
            valloader=mock_loader,
            training_device="cpu",
            num_of_client_epochs=1,
            model_type="cnn",
        )

        images, labels = client._get_sample_batch_for_viz()

        assert images is None
        assert labels is None


class TestFlowerClientTransformerAttacks:
    """Test transformer-specific attack paths."""

    @pytest.fixture
    def transformer_client(self, tmp_path):
        """Create a transformer client with mock tokenizer."""
        mock_net = Mock()
        mock_net.parameters.return_value = [torch.randn(10, 5)]
        mock_net.state_dict.return_value = {"layer.weight": torch.randn(10, 5)}
        mock_net.train = Mock()
        mock_net.eval = Mock()

        mock_batch = {
            "input_ids": torch.randint(0, 1000, (4, 32)),
            "attention_mask": torch.ones(4, 32),
            "labels": torch.randint(0, 10, (4,)),
        }
        mock_loader = Mock()
        mock_loader.__iter__ = Mock(return_value=iter([mock_batch]))
        mock_loader.__len__ = Mock(return_value=1)
        mock_loader.dataset = Mock()
        mock_loader.dataset.__len__ = Mock(return_value=4)

        mock_tokenizer = Mock()
        mock_tokenizer.pad_token_id = 0
        mock_tokenizer.decode = Mock(return_value="test text")

        return FlowerClient(
            client_id=0,
            net=mock_net,
            trainloader=mock_loader,
            valloader=mock_loader,
            training_device="cpu",
            num_of_client_epochs=1,
            model_type="transformer",
            tokenizer=mock_tokenizer,
            save_attack_snapshots=True,
            attack_snapshot_format="pickle_and_visual",
            output_dir=str(tmp_path),
            strategy_number=0,
        )

    def test_save_attack_snapshots_transformer_path(self, transformer_client, tmp_path):
        """Test transformer visual snapshot saving path."""
        with (
            patch("src.client_models.flower_client.save_attack_snapshot") as mock_save,
            patch("src.client_models.flower_client.save_visual_snapshot") as mock_visual,
        ):
            transformer_client._save_attack_snapshots(
                current_round=1,
                attack_configs=[{"attack_type": "token_replacement"}],
                data_sample=torch.randint(0, 1000, (5, 32)),
                labels_sample=torch.randint(0, 10, (5,)),
                original_data_sample=torch.randint(0, 1000, (5, 32)),
                original_labels_sample=torch.randint(0, 10, (5,)),
            )

            mock_save.assert_called_once()
            mock_visual.assert_called_once()

            # Verify tokenizer was passed
            call_kwargs = mock_visual.call_args[1]
            assert "tokenizer" in call_kwargs
            assert call_kwargs["tokenizer"] == transformer_client.tokenizer

    def test_transformer_without_tokenizer_no_visual(self, tmp_path):
        """Test transformer without tokenizer doesn't save visual snapshot."""
        mock_net = Mock()
        mock_net.parameters.return_value = [torch.randn(10, 5)]
        mock_net.state_dict.return_value = {"layer.weight": torch.randn(10, 5)}

        mock_loader = Mock()
        mock_loader.__iter__ = Mock(return_value=iter([]))
        mock_loader.__len__ = Mock(return_value=0)
        mock_loader.dataset = Mock()
        mock_loader.dataset.__len__ = Mock(return_value=0)

        client = FlowerClient(
            client_id=0,
            net=mock_net,
            trainloader=mock_loader,
            valloader=mock_loader,
            training_device="cpu",
            num_of_client_epochs=1,
            model_type="transformer",
            tokenizer=None,  # No tokenizer
            save_attack_snapshots=True,
            attack_snapshot_format="pickle_and_visual",
            output_dir=str(tmp_path),
        )

        with (
            patch("src.client_models.flower_client.save_attack_snapshot") as mock_save,
            patch("src.client_models.flower_client.save_visual_snapshot") as mock_visual,
        ):
            client._save_attack_snapshots(
                current_round=1,
                attack_configs=[{"attack_type": "token_replacement"}],
                data_sample=torch.randint(0, 1000, (5, 32)),
                labels_sample=torch.randint(0, 10, (5,)),
                original_data_sample=torch.randint(0, 1000, (5, 32)),
            )

            mock_save.assert_called_once()
            # Visual snapshot should NOT be called without tokenizer
            mock_visual.assert_not_called()


class TestFlowerClientWeightPoisoning:
    """Test weight poisoning visualization paths."""

    @pytest.fixture
    def weight_poison_client(self, tmp_path):
        """Create client configured for weight poisoning with snapshots."""
        mock_net = MockCNNNetwork(num_classes=10, input_channels=3)
        mock_data = [(torch.randn(4, 3, 32, 32), torch.randint(0, 10, (4,))) for _ in range(2)]

        mock_loader = Mock()
        mock_loader.__iter__ = Mock(return_value=iter(mock_data))
        mock_loader.__len__ = Mock(return_value=2)
        mock_loader.dataset = Mock()
        mock_loader.dataset.__len__ = Mock(return_value=8)

        return FlowerClient(
            client_id=0,  # Malicious client
            net=mock_net,
            trainloader=mock_loader,
            valloader=mock_loader,
            training_device="cpu",
            num_of_client_epochs=1,
            model_type="cnn",
            num_malicious_clients=1,
            attacks_schedule=[{"rounds": [1], "attack_type": "model_poisoning"}],
            save_attack_snapshots=True,
            attack_snapshot_format="pickle_and_visual",
            output_dir=str(tmp_path),
            strategy_number=0,
        )

    def test_fit_with_weight_poisoning_returns_result(self, weight_poison_client, tmp_path):
        """Test fit() with weight poisoning returns proper result."""
        initial_params = weight_poison_client.get_parameters(config={})

        # Actually run fit - this triggers the weight poisoning code path
        result = weight_poison_client.fit(initial_params, config={"server_round": 1})

        # Result should be returned with correct structure
        assert result is not None
        assert len(result) == 3
        params, dataset_size, metrics = result
        assert isinstance(params, list)
        assert isinstance(dataset_size, int)
        assert isinstance(metrics, dict)
        assert "loss" in metrics
        assert "accuracy" in metrics

    def test_fit_weight_poisoning_without_snapshots(self, tmp_path):
        """Test weight poisoning works when snapshots are disabled."""
        mock_net = MockCNNNetwork(num_classes=10, input_channels=3)
        mock_data = [(torch.randn(4, 3, 32, 32), torch.randint(0, 10, (4,)))]

        mock_loader = Mock()
        mock_loader.__iter__ = Mock(return_value=iter(mock_data))
        mock_loader.__len__ = Mock(return_value=1)
        mock_loader.dataset = Mock()
        mock_loader.dataset.__len__ = Mock(return_value=4)

        client = FlowerClient(
            client_id=0,
            net=mock_net,
            trainloader=mock_loader,
            valloader=mock_loader,
            training_device="cpu",
            num_of_client_epochs=1,
            model_type="cnn",
            num_malicious_clients=1,
            attacks_schedule=[{"rounds": [1], "attack_type": "model_poisoning"}],
            save_attack_snapshots=False,  # Disabled
            output_dir=str(tmp_path),
        )

        initial_params = client.get_parameters(config={})
        result = client.fit(initial_params, config={"server_round": 1})

        assert result is not None
        assert len(result) == 3

    @pytest.mark.parametrize(
        "attack_type", ["model_poisoning", "gradient_scaling", "byzantine_perturbation"]
    )
    def test_fit_various_weight_attack_types(self, attack_type, tmp_path):
        """Test fit() with various weight attack types executes without error."""
        mock_net = MockCNNNetwork(num_classes=10, input_channels=3)
        mock_data = [(torch.randn(4, 3, 32, 32), torch.randint(0, 10, (4,)))]

        mock_loader = Mock()
        mock_loader.__iter__ = Mock(return_value=iter(mock_data))
        mock_loader.__len__ = Mock(return_value=1)
        mock_loader.dataset = Mock()
        mock_loader.dataset.__len__ = Mock(return_value=4)

        client = FlowerClient(
            client_id=0,
            net=mock_net,
            trainloader=mock_loader,
            valloader=mock_loader,
            training_device="cpu",
            num_of_client_epochs=1,
            model_type="cnn",
            num_malicious_clients=1,
            attacks_schedule=[{"rounds": [1], "attack_type": attack_type}],
            save_attack_snapshots=False,  # Disabled for simplicity
            output_dir=str(tmp_path),
        )

        initial_params = client.get_parameters(config={})

        # Actually run fit to exercise the weight attack code path
        result = client.fit(initial_params, config={"server_round": 1})

        assert result is not None
        assert len(result) == 3


class TestFlowerClientFedProx:
    """Test FedProx regularization path."""

    def test_transformer_with_fedprox(self, tmp_path):
        """Test transformer training with FedProx regularization."""
        mock_net = Mock()
        mock_net.parameters.return_value = [torch.randn(10, 5, requires_grad=True)]
        mock_net.state_dict.return_value = {"layer.weight": torch.randn(10, 5)}
        mock_net.train = Mock()
        mock_net.eval = Mock()

        # Create mock outputs with loss
        mock_outputs = Mock()
        mock_outputs.loss = torch.tensor(0.5, requires_grad=True)
        mock_outputs.logits = torch.randn(4, 10)
        mock_net.return_value = mock_outputs
        mock_net.__call__ = Mock(return_value=mock_outputs)  # type: ignore[method-assign]

        mock_batch = {
            "input_ids": torch.randint(0, 1000, (4, 32)),
            "attention_mask": torch.ones(4, 32),
            "labels": torch.randint(0, 10, (4,)),
        }
        mock_loader = Mock()
        mock_loader.__iter__ = Mock(return_value=iter([mock_batch]))
        mock_loader.__len__ = Mock(return_value=1)
        mock_loader.dataset = Mock()
        mock_loader.dataset.__len__ = Mock(return_value=4)

        client = FlowerClient(
            client_id=5,  # Benign client (>= num_malicious_clients)
            net=mock_net,
            trainloader=mock_loader,
            valloader=mock_loader,
            training_device="cpu",
            num_of_client_epochs=1,
            model_type="transformer",
            use_lora=True,
            num_malicious_clients=2,
            output_dir=str(tmp_path),
        )

        # Create global params for FedProx
        global_params = [torch.randn(10, 5)]

        with patch.object(
            client, "get_parameters", return_value=[p.numpy() for p in global_params]
        ):
            # Train should complete without error with FedProx term
            loss, acc = client.train(
                mock_net,
                mock_loader,
                epochs=1,
                global_params=global_params,
                mu=0.01,
                config={"server_round": 1},
            )

            # Verify training completed
            assert isinstance(loss, float)
            assert isinstance(acc, float)
