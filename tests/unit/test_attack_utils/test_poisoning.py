"""Unit tests for attack_utils.poisoning module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import torch

from intellifl.attack_utils.poisoning import (
    DATA_ATTACK_TYPES,
    apply_backdoor_trigger,
    apply_gaussian_noise,
    apply_label_flipping,
    apply_poisoning_attack,
    apply_targeted_label_flipping,
    apply_token_replacement,
    should_poison_this_round,
)
from tests.common import pytest


class TestApplyLabelFlipping:
    """Tests for apply_label_flipping."""

    def test_single_class_no_flipping(self):
        """Tests that single class dataset returns unchanged."""
        labels = torch.tensor([0, 0, 0, 0, 0])
        original_labels = labels.clone()

        result = apply_label_flipping(labels, num_classes=1)

        assert torch.equal(result, original_labels)

    def test_class_level_mapping(self):
        """Tests that all samples of each class map to the same random class."""
        labels = torch.tensor([0, 0, 0, 1, 1, 1, 2, 2, 2])
        num_classes = 5

        result = apply_label_flipping(labels, num_classes=num_classes)

        class_0_values = result[labels == 0].unique()
        assert len(class_0_values) == 1
        assert class_0_values[0] != 0

        class_1_values = result[labels == 1].unique()
        assert len(class_1_values) == 1
        assert class_1_values[0] != 1

        class_2_values = result[labels == 2].unique()
        assert len(class_2_values) == 1
        assert class_2_values[0] != 2

    def test_all_labels_modified(self):
        """Tests that all labels are modified."""
        labels = torch.tensor([0, 1, 2, 3, 4])
        num_classes = 10

        result = apply_label_flipping(labels, num_classes=num_classes)

        assert not torch.equal(result, labels)

        assert torch.all(result >= 0)
        assert torch.all(result < num_classes)

    def test_label_values_within_range(self):
        """Tests that flipped labels are within valid class range."""
        labels = torch.tensor([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        num_classes = 10

        result = apply_label_flipping(labels, num_classes=num_classes)

        assert torch.all(result >= 0)
        assert torch.all(result < num_classes)

    def test_no_self_mapping(self):
        """Tests that no class maps to itself."""
        labels = torch.tensor([0, 1, 2, 3, 4])
        num_classes = 10

        result = apply_label_flipping(labels, num_classes=num_classes)

        for original_class in labels.unique():
            mapped_class = result[labels == original_class][0]
            assert mapped_class != original_class

    def test_two_class_swapping(self):
        """Tests label flipping with only 2 classes."""
        labels = torch.tensor([0, 0, 1, 1])
        num_classes = 2

        result = apply_label_flipping(labels, num_classes=num_classes)

        assert torch.all(result[labels == 0] == 1)
        assert torch.all(result[labels == 1] == 0)

    def test_same_client_id_yields_stable_permutation(self):
        """Same client_id must produce identical flip mapping across calls.

        The dynamic attack_schedule path invokes apply_label_flipping once per
        batch; without seeding, every batch saw a fresh permutation and the
        model averaged the noise out. A stable per-client mapping is the
        whole point of the client_id parameter.
        """
        labels = torch.tensor([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        num_classes = 10

        first = apply_label_flipping(labels, num_classes=num_classes, client_id=7)
        torch.randperm(num_classes)
        second = apply_label_flipping(labels, num_classes=num_classes, client_id=7)
        third = apply_label_flipping(labels, num_classes=num_classes, client_id=7)

        assert torch.equal(first, second)
        assert torch.equal(first, third)

    def test_different_client_ids_diverge(self):
        """Different malicious clients must (overwhelmingly) get different mappings.

        With 10 classes and no self-mapping, the chance of two arbitrary seeds
        landing on the same permutation is ~1/9! — collision is theoretically
        possible but vanishingly rare for the small fixed seeds used here.
        """
        labels = torch.tensor([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        num_classes = 10

        result_client_0 = apply_label_flipping(labels, num_classes=num_classes, client_id=0)
        result_client_1 = apply_label_flipping(labels, num_classes=num_classes, client_id=1)
        result_client_2 = apply_label_flipping(labels, num_classes=num_classes, client_id=2)

        assert not torch.equal(result_client_0, result_client_1)
        assert not torch.equal(result_client_0, result_client_2)
        assert not torch.equal(result_client_1, result_client_2)

    def test_client_id_independent_of_global_rng(self):
        """Seeded permutation must not be perturbed by global RNG state changes.

        Direct verification of the bug: if the function leaked into the global
        generator (or read from it), advancing torch.manual_seed between calls
        would change the result.
        """
        labels = torch.tensor([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        num_classes = 10

        torch.manual_seed(1)
        seeded_call = apply_label_flipping(labels, num_classes=num_classes, client_id=3)

        torch.manual_seed(999)
        same_after_global_reseed = apply_label_flipping(
            labels, num_classes=num_classes, client_id=3
        )

        assert torch.equal(seeded_call, same_after_global_reseed)

    def test_client_id_none_preserves_legacy_random_behavior(self):
        """client_id=None must use the global RNG, matching pre-fix behavior."""
        labels = torch.tensor([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        num_classes = 10

        torch.manual_seed(42)
        first = apply_label_flipping(labels, num_classes=num_classes)

        torch.manual_seed(42)
        second = apply_label_flipping(labels, num_classes=num_classes)

        assert torch.equal(first, second)


class TestApplyGaussianNoise:
    """Tests for apply_gaussian_noise."""

    def test_no_poisoning_when_attack_ratio_zero(self):
        """Tests that no samples are poisoned when attack_ratio is 0."""
        images = torch.rand(10, 3, 28, 28)
        original_images = images.clone()

        result = apply_gaussian_noise(images, attack_ratio=0.0)

        assert torch.allclose(result, original_images)

    def test_no_poisoning_when_num_to_poison_zero(self):
        """Tests that no samples are poisoned when calculated num_to_poison is 0."""
        images = torch.rand(2, 3, 28, 28)
        original_images = images.clone()

        result = apply_gaussian_noise(images, attack_ratio=0.3)

        assert torch.allclose(result, original_images)

    def test_gaussian_noise_with_mean_std(self):
        """Tests Gaussian noise addition with mean and std parameters."""
        images = torch.rand(10, 3, 28, 28)
        original_images = images.clone()

        result = apply_gaussian_noise(images, mean=0.0, std=0.1, attack_ratio=1.0)

        assert not torch.allclose(result, original_images, rtol=1e-4)

        assert torch.all(result >= 0.0)
        assert torch.all(result <= 1.0)

    def test_gaussian_noise_with_snr(self):
        """Tests Gaussian noise addition with SNR parameter."""
        images = torch.rand(10, 3, 28, 28) + 0.1
        original_images = images.clone()

        result = apply_gaussian_noise(images, target_noise_snr=20.0, attack_ratio=1.0)

        assert not torch.allclose(result, original_images, rtol=1e-4)

        assert torch.all(result >= 0.0)
        assert torch.all(result <= 1.0)

    def test_partial_poisoning(self):
        """Tests that only the specified fraction of samples are poisoned."""
        images = torch.rand(10, 3, 28, 28)
        attack_ratio = 0.5

        result = apply_gaussian_noise(images, std=0.5, attack_ratio=attack_ratio)

        expected_poisoned = int(10 * attack_ratio)
        assert expected_poisoned == 5

        assert torch.all(result >= 0.0)
        assert torch.all(result <= 1.0)

    def test_noise_clamping(self):
        """Tests that noisy images are properly clamped to [0, 1]."""
        images = torch.ones(5, 1, 10, 10) * 0.9

        result = apply_gaussian_noise(images, mean=0.0, std=1.0, attack_ratio=1.0)

        assert torch.all(result >= 0.0)
        assert torch.all(result <= 1.0)


class TestApplyTokenReplacement:
    """Tests for apply_token_replacement."""

    def test_no_replacement_when_prob_zero(self):
        """Tests that no tokens are replaced when replacement_prob is 0."""
        tokens = torch.tensor([[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]])
        original_tokens = tokens.clone()

        result = apply_token_replacement(tokens, replacement_prob=0.0)

        assert torch.equal(result, original_tokens)

    def test_no_replacement_when_prob_negative(self):
        """Tests that no tokens are replaced when replacement_prob is negative."""
        tokens = torch.tensor([[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]])
        original_tokens = tokens.clone()

        result = apply_token_replacement(tokens, replacement_prob=-0.5)

        assert torch.equal(result, original_tokens)

    def test_partial_replacement(self):
        """Tests partial token replacement."""
        torch.manual_seed(42)
        tokens = torch.tensor([[1, 2, 3, 4, 5]] * 100)

        result = apply_token_replacement(
            tokens,
            replacement_prob=0.3,
            target_token_ids=[2, 3, 4],
            replacement_token_ids=[20, 30, 40],
        )

        changed = not torch.equal(result, tokens)
        assert changed

    def test_full_replacement(self):
        """Tests full token replacement."""
        tokens = torch.tensor([[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]])

        result = apply_token_replacement(
            tokens,
            replacement_prob=1.0,
            target_token_ids=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            replacement_token_ids=[100, 200, 300, 400, 500],
        )

        num_changed = (result != tokens).sum().item()
        assert num_changed > 0

    def test_token_values_within_vocab(self):
        """Tests that replaced tokens are from the replacement list."""
        tokens = torch.tensor([[1, 2, 3, 4, 5]] * 10)
        target_token_ids = [2, 3, 4]
        replacement_token_ids = [100, 200, 300]

        result = apply_token_replacement(
            tokens,
            replacement_prob=1.0,
            target_token_ids=target_token_ids,
            replacement_token_ids=replacement_token_ids,
        )

        for batch_idx in range(result.shape[0]):
            for seq_idx in range(result.shape[1]):
                token = result[batch_idx, seq_idx].item()
                if token not in [1, 5]:
                    assert token in replacement_token_ids


class TestShouldPoisonThisRound:
    """Tests for should_poison_this_round."""

    def test_empty_schedule_returns_false(self):
        """Tests that an empty or None schedule returns False."""
        should_poison, attacks = should_poison_this_round(5, 0, None)
        assert should_poison is False
        assert len(attacks) == 0

        should_poison, attacks = should_poison_this_round(5, 0, [])
        assert should_poison is False
        assert len(attacks) == 0

    def test_specific_selection_strategy(self):
        """Tests specific client selection strategy."""
        schedule = [
            {
                "start_round": 1,
                "end_round": 10,
                "attack_type": "label_flipping",
                "selection_strategy": "specific",
                "malicious_client_ids": [0, 2, 4],
            }
        ]

        should_poison, attacks = should_poison_this_round(5, 0, schedule)
        assert should_poison is True
        assert len(attacks) == 1

        should_poison, attacks = should_poison_this_round(5, 1, schedule)
        assert should_poison is False
        assert len(attacks) == 0

    def test_random_selection_strategy(self):
        """Tests random client selection strategy."""
        schedule = [
            {
                "start_round": 1,
                "end_round": 10,
                "attack_type": "label_flipping",
                "selection_strategy": "random",
                "_selected_clients": [1, 3, 5],
            }
        ]

        should_poison, attacks = should_poison_this_round(5, 1, schedule)
        assert should_poison is True
        assert len(attacks) == 1

        should_poison, attacks = should_poison_this_round(5, 0, schedule)
        assert should_poison is False
        assert len(attacks) == 0

    def test_percentage_selection_strategy(self):
        """Tests percentage client selection strategy."""
        schedule = [
            {
                "start_round": 1,
                "end_round": 10,
                "attack_type": "gaussian_noise",
                "selection_strategy": "percentage",
                "_selected_clients": [0, 2, 4],
                "target_noise_snr": 10.0,
            }
        ]

        should_poison, attacks = should_poison_this_round(5, 2, schedule)
        assert should_poison is True
        assert len(attacks) == 1

        should_poison, attacks = should_poison_this_round(5, 1, schedule)
        assert should_poison is False
        assert len(attacks) == 0

    def test_round_range_filtering(self):
        """Tests that attacks are only active within their round range."""
        schedule = [
            {
                "start_round": 5,
                "end_round": 10,
                "attack_type": "label_flipping",
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
            }
        ]

        should_poison, attacks = should_poison_this_round(3, 0, schedule)
        assert should_poison is False

        should_poison, attacks = should_poison_this_round(7, 0, schedule)
        assert should_poison is True

        should_poison, attacks = should_poison_this_round(11, 0, schedule)
        assert should_poison is False

    def test_attack_type_deduplication(self):
        """Tests that duplicate attack types use first-match-wins."""
        schedule = [
            {
                "start_round": 1,
                "end_round": 10,
                "attack_type": "label_flipping",
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
            },
            {
                "start_round": 1,
                "end_round": 10,
                "attack_type": "label_flipping",
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
            },
        ]

        should_poison, attacks = should_poison_this_round(5, 0, schedule)

        assert len(attacks) == 1

    def test_multiple_attack_types(self):
        """Tests that different attack types can be returned together."""
        schedule = [
            {
                "start_round": 1,
                "end_round": 10,
                "attack_type": "label_flipping",
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
            },
            {
                "start_round": 1,
                "end_round": 10,
                "attack_type": "gaussian_noise",
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
                "target_noise_snr": 15.0,
            },
        ]

        should_poison, attacks = should_poison_this_round(5, 0, schedule)

        assert len(attacks) == 2
        attack_types = {a["attack_type"] for a in attacks}
        assert attack_types == {"label_flipping", "gaussian_noise"}

    def test_missing_attack_type_not_included(self):
        """Tests that attack entries without attack_type are not included."""
        schedule = [
            {
                "start_round": 1,
                "end_round": 10,
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
            }
        ]

        should_poison, attacks = should_poison_this_round(5, 0, schedule)

        assert should_poison is False
        assert len(attacks) == 0


class TestApplyPoisoningAttack:
    """Tests for apply_poisoning_attack."""

    def test_label_flipping_attack(self):
        """Tests label flipping attack application."""
        images = torch.rand(10, 1, 28, 28)
        labels = torch.tensor([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        original_labels = labels.clone()

        attack_config = {
            "attack_type": "label_flipping",
        }
        num_classes = 10

        result_images, result_labels = apply_poisoning_attack(
            images, labels, attack_config, num_classes=num_classes
        )

        assert torch.allclose(result_images, images)

        assert not torch.equal(result_labels, original_labels)

        assert torch.all(result_labels >= 0)
        assert torch.all(result_labels < num_classes)

    def test_label_flipping_attack_threads_client_id(self):
        """apply_poisoning_attack must forward client_id to the dispatcher."""
        labels = torch.tensor([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        original_labels = labels.clone()
        num_classes = 10

        attack_config = {"attack_type": "label_flipping"}

        _, first = apply_poisoning_attack(
            torch.rand(10, 1, 28, 28),
            original_labels.clone(),
            attack_config,
            num_classes=num_classes,
            client_id=4,
        )
        _, second = apply_poisoning_attack(
            torch.rand(10, 1, 28, 28),
            original_labels.clone(),
            attack_config,
            num_classes=num_classes,
            client_id=4,
        )

        assert torch.equal(first, second)

    def test_gaussian_noise_attack_with_snr(self):
        """Tests Gaussian noise attack with SNR parameter."""
        images = torch.rand(10, 3, 28, 28) + 0.1
        labels = torch.tensor([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        original_images = images.clone()

        attack_config = {
            "attack_type": "gaussian_noise",
            "target_noise_snr": 20.0,
            "attack_ratio": 1.0,
        }

        result_images, result_labels = apply_poisoning_attack(images, labels, attack_config)

        assert not torch.allclose(result_images, original_images, rtol=1e-4)

        assert torch.equal(result_labels, labels)

    def test_gaussian_noise_attack_with_mean_std(self):
        """Tests Gaussian noise attack with mean/std parameters."""
        images = torch.rand(10, 3, 28, 28)
        labels = torch.tensor([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        original_images = images.clone()

        attack_config = {
            "attack_type": "gaussian_noise",
            "mean": 0.0,
            "std": 0.1,
            "attack_ratio": 1.0,
        }

        result_images, result_labels = apply_poisoning_attack(images, labels, attack_config)

        assert not torch.allclose(result_images, original_images, rtol=1e-4)

        assert torch.equal(result_labels, labels)

    def test_token_replacement_attack(self):
        """Tests token replacement attack application."""
        tokens = torch.tensor([[1, 2, 3, 4, 5]] * 10)
        labels = torch.tensor([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])

        attack_config = {
            "attack_type": "token_replacement",
            "replacement_prob": 1.0,
            "target_token_ids": [1, 2, 3, 4, 5],
            "replacement_token_ids": [100, 200, 300, 400, 500],
        }

        result_tokens, result_labels = apply_poisoning_attack(tokens, labels, attack_config)

        assert not torch.equal(result_tokens, tokens)

        assert torch.equal(result_labels, labels)

    def test_old_nested_format_raises_error(self):
        """Tests that old nested config format raises a helpful error."""
        images = torch.rand(10, 1, 28, 28)
        labels = torch.tensor([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])

        old_config1 = {
            "type": "label_flipping",
        }

        with pytest.raises(ValueError, match="old nested attack config format"):
            apply_poisoning_attack(images, labels, old_config1)

        old_config2 = {
            "type": "label_flipping",
        }

        with pytest.raises(ValueError, match="old nested attack config format"):
            apply_poisoning_attack(images, labels, old_config2)

    def test_unknown_attack_type_does_nothing(self):
        """Tests that an unknown attack type returns data unchanged."""
        images = torch.rand(10, 1, 28, 28)
        labels = torch.tensor([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        original_images = images.clone()
        original_labels = labels.clone()

        attack_config = {"attack_type": "unknown_attack"}

        result_images, result_labels = apply_poisoning_attack(images, labels, attack_config)

        assert torch.allclose(result_images, original_images)
        assert torch.equal(result_labels, original_labels)

    def test_requires_num_classes(self):
        """Tests that num_classes is required for label_flipping."""
        images = torch.rand(10, 1, 28, 28)
        labels = torch.tensor([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])

        attack_config = {
            "attack_type": "label_flipping",
        }

        with pytest.raises(ValueError, match="num_classes"):
            apply_poisoning_attack(images, labels, attack_config)


class TestTokenReplacementWithVocabulary:
    """Tests for token replacement using vocabulary and tokenizer."""

    @pytest.fixture
    def mock_tokenizer(self):
        """Creates a mock tokenizer."""
        tokenizer = MagicMock()

        def encode_side_effect(text, add_special_tokens=False):
            mapping = {
                "hello": [101],
                "world": [102],
                "foo": [103],
                "bar": [104],
            }
            return mapping.get(text, [])

        tokenizer.encode.side_effect = encode_side_effect
        return tokenizer

    @patch("intellifl.attack_utils.poisoning.get_vocabulary")
    @patch("intellifl.attack_utils.poisoning.get_replacement_strategy")
    def test_token_replacement_with_vocab_integration(
        self, mock_get_strategy, mock_get_vocab, mock_tokenizer
    ):
        """Tests the full path where vocabulary and tokenizer are used to setup the attack."""
        mock_get_vocab.return_value = ["hello", "world"]
        mock_get_strategy.return_value = ["foo", "bar"]

        tokens = torch.tensor(
            [
                [101, 999, 102, 999],
                [999, 999, 999, 999],
            ]
        )
        labels = torch.zeros(2)

        attack_config = {
            "attack_type": "token_replacement",
            "target_vocabulary": "test_vocab",
            "replacement_strategy": "test_strategy",
            "replacement_prob": 1.0,
        }

        result_tokens, result_labels = apply_poisoning_attack(
            tokens, labels, attack_config, tokenizer=mock_tokenizer
        )

        mock_get_vocab.assert_called_with("test_vocab")
        mock_get_strategy.assert_called_with("test_strategy")

        replacements = {103, 104}

        assert result_tokens[0, 0].item() in replacements

        assert result_tokens[0, 2].item() in replacements

        assert result_tokens[0, 1].item() == 999

    def test_missing_vocabulary_error(self, mock_tokenizer):
        """Tests error raised when target_vocabulary is missing."""
        attack_config = {
            "attack_type": "token_replacement",
        }

        with pytest.raises(ValueError, match="requires 'target_vocabulary'"):
            apply_poisoning_attack(
                torch.zeros(1), torch.zeros(1), attack_config, tokenizer=mock_tokenizer
            )


class TestDataAttackTypes:
    """Tests DATA_ATTACK_TYPES registry."""

    def test_data_attack_types_contains_expected(self):
        """Verifies DATA_ATTACK_TYPES includes all expected types."""
        expected = {
            "label_flipping",
            "targeted_label_flipping",
            "gaussian_noise",
            "token_replacement",
            "backdoor_trigger",
        }
        assert expected == DATA_ATTACK_TYPES


class TestApplyTargetedLabelFlipping:
    """Tests for apply_targeted_label_flipping."""

    def test_flips_source_to_target(self):
        """Verifies all source_class labels are flipped to target_class."""
        labels = torch.tensor([0, 0, 1, 1, 2, 2, 3, 3])

        result = apply_targeted_label_flipping(labels, source_class=0, target_class=5)

        assert torch.all(result[labels == 0] == 5)
        # Non-source labels unchanged
        assert torch.all(result[labels == 1] == 1)
        assert torch.all(result[labels == 2] == 2)
        assert torch.all(result[labels == 3] == 3)

    def test_partial_flip_ratio(self):
        """Verifies flip_ratio controls fraction of source samples flipped."""
        torch.manual_seed(42)
        labels = torch.tensor([0] * 100 + [1] * 100)

        result = apply_targeted_label_flipping(
            labels, source_class=0, target_class=9, flip_ratio=0.5
        )

        flipped = (result[:100] == 9).sum().item()
        assert 40 <= flipped <= 60

    def test_no_change_when_source_absent(self):
        """Verifies no changes when source_class not present."""
        labels = torch.tensor([1, 2, 3, 4])

        result = apply_targeted_label_flipping(labels, source_class=0, target_class=9)

        assert torch.equal(result, labels)

    def test_preserves_tensor_shape(self):
        """Verifies output shape matches input."""
        labels = torch.tensor([0, 1, 2, 3, 4])

        result = apply_targeted_label_flipping(labels, source_class=0, target_class=9)

        assert result.shape == labels.shape


class TestApplyBackdoorTrigger:
    """Tests for apply_backdoor_trigger."""

    def test_stamps_square_trigger(self):
        """Verifies square trigger pattern is applied."""
        torch.manual_seed(42)
        images = torch.zeros(10, 1, 28, 28)
        labels = torch.zeros(10, dtype=torch.long)

        poisoned_images, poisoned_labels = apply_backdoor_trigger(
            images,
            labels,
            target_class=7,
            trigger_pattern="square",
            trigger_size=4,
            trigger_position="bottom_right",
            poison_ratio=1.0,
        )

        # All images should have the trigger in bottom-right
        for i in range(10):
            assert poisoned_images[i, 0, 24:28, 24:28].sum() > 0
            assert poisoned_labels[i] == 7

    def test_stamps_cross_trigger(self):
        """Verifies cross trigger pattern is applied."""
        torch.manual_seed(42)
        images = torch.zeros(10, 1, 28, 28)
        labels = torch.zeros(10, dtype=torch.long)

        poisoned_images, poisoned_labels = apply_backdoor_trigger(
            images,
            labels,
            target_class=3,
            trigger_pattern="cross",
            trigger_size=4,
            trigger_position="top_left",
            poison_ratio=1.0,
        )

        # Cross pattern should modify some pixels in the trigger region
        for i in range(10):
            trigger_region = poisoned_images[i, 0, 0:4, 0:4]
            assert trigger_region.sum() > 0
            assert poisoned_labels[i] == 3

    def test_partial_poisoning(self):
        """Verifies poison_ratio controls fraction of poisoned images."""
        torch.manual_seed(42)
        images = torch.zeros(100, 1, 28, 28)
        labels = torch.zeros(100, dtype=torch.long)

        poisoned_images, poisoned_labels = apply_backdoor_trigger(
            images,
            labels,
            target_class=5,
            poison_ratio=0.1,
        )

        num_poisoned = (poisoned_labels == 5).sum().item()
        assert num_poisoned == 10

    def test_relabels_to_target_class(self):
        """Verifies poisoned samples are relabeled to target_class."""
        torch.manual_seed(42)
        images = torch.rand(20, 3, 32, 32)
        labels = torch.arange(20) % 10

        _, poisoned_labels = apply_backdoor_trigger(
            images,
            labels,
            target_class=9,
            poison_ratio=0.5,
        )

        num_target = (poisoned_labels == 9).sum().item()
        assert num_target >= 10

    def test_trigger_positions(self):
        """Verifies different trigger positions work."""
        for position in ("bottom_right", "top_left", "center", "random"):
            torch.manual_seed(42)
            images = torch.zeros(5, 1, 28, 28)
            labels = torch.zeros(5, dtype=torch.long)

            poisoned_images, _ = apply_backdoor_trigger(
                images,
                labels,
                target_class=1,
                trigger_position=position,
                poison_ratio=1.0,
            )

            # At least some pixels should be modified
            assert poisoned_images.sum() > 0

    def test_invalid_trigger_position_raises(self):
        """Verifies ValueError for unknown trigger position."""
        images = torch.zeros(5, 1, 28, 28)
        labels = torch.zeros(5, dtype=torch.long)

        with pytest.raises(ValueError, match="Unknown trigger_position"):
            apply_backdoor_trigger(
                images,
                labels,
                target_class=1,
                trigger_position="invalid",
            )

    def test_invalid_trigger_pattern_raises(self):
        """Verifies ValueError for unknown trigger pattern."""
        images = torch.zeros(5, 1, 28, 28)
        labels = torch.zeros(5, dtype=torch.long)

        with pytest.raises(ValueError, match="Unknown trigger_pattern"):
            apply_backdoor_trigger(
                images,
                labels,
                target_class=1,
                trigger_pattern="invalid",
            )

    def test_preserves_shapes(self):
        """Verifies output shapes match input."""
        images = torch.rand(10, 3, 32, 32)
        labels = torch.randint(0, 10, (10,))

        poisoned_images, poisoned_labels = apply_backdoor_trigger(
            images,
            labels,
            target_class=0,
        )

        assert poisoned_images.shape == images.shape
        assert poisoned_labels.shape == labels.shape

    def test_multichannel_trigger(self):
        """Verifies trigger is applied across all channels."""
        torch.manual_seed(42)
        images = torch.zeros(5, 3, 28, 28)
        labels = torch.zeros(5, dtype=torch.long)

        poisoned_images, _ = apply_backdoor_trigger(
            images,
            labels,
            target_class=1,
            trigger_size=4,
            trigger_position="bottom_right",
            poison_ratio=1.0,
        )

        # All 3 channels should have the trigger
        for c in range(3):
            assert poisoned_images[0, c, 24:28, 24:28].sum() > 0


class TestDispatchNewDataAttacks:
    """Tests dispatcher with new data attack types."""

    def test_dispatch_targeted_label_flipping(self):
        """Verifies dispatcher handles targeted_label_flipping."""
        images = torch.rand(10, 1, 28, 28)
        labels = torch.tensor([0, 0, 0, 1, 1, 1, 2, 2, 2, 3])

        attack_config = {
            "attack_type": "targeted_label_flipping",
            "source_class": 0,
            "target_class": 9,
        }

        result_images, result_labels = apply_poisoning_attack(images, labels, attack_config)

        assert torch.allclose(result_images, images)
        assert torch.all(result_labels[labels == 0] == 9)

    def test_dispatch_targeted_label_flipping_missing_params(self):
        """Verifies dispatcher raises error for missing required params."""
        images = torch.rand(5, 1, 28, 28)
        labels = torch.zeros(5, dtype=torch.long)

        attack_config = {"attack_type": "targeted_label_flipping"}

        with pytest.raises(ValueError, match="source_class.*target_class"):
            apply_poisoning_attack(images, labels, attack_config)

    def test_dispatch_backdoor_trigger(self):
        """Verifies dispatcher handles backdoor_trigger."""
        torch.manual_seed(42)
        images = torch.zeros(20, 1, 28, 28)
        labels = torch.zeros(20, dtype=torch.long)

        attack_config = {
            "attack_type": "backdoor_trigger",
            "target_class": 7,
            "poison_ratio": 0.5,
        }

        result_images, result_labels = apply_poisoning_attack(images, labels, attack_config)

        num_poisoned = (result_labels == 7).sum().item()
        assert num_poisoned == 10

    def test_dispatch_backdoor_trigger_missing_target_class(self):
        """Verifies dispatcher raises error when target_class missing."""
        images = torch.rand(5, 1, 28, 28)
        labels = torch.zeros(5, dtype=torch.long)

        attack_config = {"attack_type": "backdoor_trigger"}

        with pytest.raises(ValueError, match="target_class"):
            apply_poisoning_attack(images, labels, attack_config)
