"""
Utility functions for applying poisoning attacks to datasets.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import torch

from intellifl.attack_utils.vocabularies.registry import (
    get_replacement_strategy,
    get_vocabulary,
)

# ---------------------------------------------------------------------------
# Attack type registry
# ---------------------------------------------------------------------------

DATA_ATTACK_TYPES = frozenset(
    [
        "label_flipping",
        "targeted_label_flipping",
        "gaussian_noise",
        "token_replacement",
        "backdoor_trigger",
    ]
)


# ---------------------------------------------------------------------------
# Core attack implementations
# ---------------------------------------------------------------------------


def apply_label_flipping(
    labels: torch.Tensor,
    num_classes: int,
) -> torch.Tensor:
    """Apply bijective label flipping where each class maps to exactly one other class.

    Args:
        labels: Input label tensor to flip.
        num_classes: Total number of classes in the dataset.

    Returns:
        Modified label tensor with all classes remapped.
    """
    perm = torch.randperm(num_classes).tolist()

    # Ensure no class maps to itself
    for i in range(num_classes):
        if perm[i] == i:
            swap_idx = (i + 1) % num_classes
            perm[i], perm[swap_idx] = perm[swap_idx], perm[i]

    modified_labels = labels.clone()
    for src_class in range(num_classes):
        modified_labels[labels == src_class] = perm[src_class]

    return modified_labels


def apply_targeted_label_flipping(
    labels: torch.Tensor,
    source_class: int,
    target_class: int,
    flip_ratio: float = 1.0,
) -> torch.Tensor:
    """Flip labels from a specific source class to a specific target class.

    Unlike random permutation flipping, this enables targeted misclassification
    attacks (e.g., 'stop sign' -> 'speed limit', or '9' -> '1').

    Args:
        labels: Input label tensor.
        source_class: Class to flip FROM.
        target_class: Class to flip TO.
        flip_ratio: Fraction of source_class samples to flip. Defaults to 1.0.

    Returns:
        Modified label tensor with targeted flips applied.
    """
    modified = labels.clone()
    source_mask = labels == source_class

    if flip_ratio < 1.0:
        num_source = source_mask.sum().item()
        num_to_flip = max(1, int(num_source * flip_ratio))
        indices = torch.where(source_mask)[0]
        selected = indices[torch.randperm(len(indices))[:num_to_flip]]
        source_mask = torch.zeros_like(labels, dtype=torch.bool)
        source_mask[selected] = True

    modified[source_mask] = target_class
    return modified


def apply_gaussian_noise(
    images: torch.Tensor,
    mean: float = 0.0,
    std: float = 0.1,
    target_noise_snr: float | None = None,
    attack_ratio: float = 1.0,
) -> torch.Tensor:
    """Add Gaussian noise to images using either SNR targeting or direct mean/std.

    Args:
        images: Input image tensor of shape (N, C, H, W).
        mean: Noise mean when using direct mode. Defaults to 0.0.
        std: Noise standard deviation when using direct mode. Defaults to 0.1.
        target_noise_snr: Target signal-to-noise ratio in dB. If provided, overrides mean/std.
        attack_ratio: Fraction of images to poison. Defaults to 1.0.

    Returns:
        Poisoned image tensor with values clamped to [0, 1].
    """
    num_samples = images.shape[0]
    num_to_poison = int(num_samples * attack_ratio)

    if num_to_poison == 0:
        return images

    indices = torch.randperm(num_samples)[:num_to_poison]
    poisoned_images = images.clone()

    if target_noise_snr is not None:
        signal_power = torch.mean(poisoned_images[indices] ** 2, dim=(1, 2, 3), keepdim=True)
        noise_power = signal_power / (10 ** (target_noise_snr / 10))
        noise = torch.randn_like(poisoned_images[indices]) * torch.sqrt(noise_power)
    else:
        noise = torch.randn_like(poisoned_images[indices]) * std + mean

    poisoned_images[indices] = torch.clamp(poisoned_images[indices] + noise, 0, 1)
    return poisoned_images


def apply_backdoor_trigger(
    images: torch.Tensor,
    labels: torch.Tensor,
    target_class: int,
    trigger_pattern: str = "square",
    trigger_size: int = 4,
    trigger_position: str = "bottom_right",
    trigger_value: float = 1.0,
    poison_ratio: float = 0.1,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Inject a pixel-pattern trigger into a subset of images and relabel them.

    Based on BadNets (Gu et al., 2017). Stamps a small visual pattern onto
    a fraction of training images and relabels them to the target class. The
    model learns to associate the trigger pattern with the target class,
    creating a backdoor that activates at inference time.

    Args:
        images: Image tensor of shape (N, C, H, W).
        labels: Label tensor of shape (N,).
        target_class: The class the backdoor should trigger.
        trigger_pattern: Pattern type -- ``"square"`` (solid block) or
            ``"cross"`` (X-shaped pattern).
        trigger_size: Size of trigger in pixels (width and height).
        trigger_position: Where to stamp the trigger -- ``"bottom_right"``,
            ``"top_left"``, ``"center"``, or ``"random"``.
        trigger_value: Pixel intensity of the trigger. Defaults to 1.0 (white).
        poison_ratio: Fraction of images to stamp with the trigger.

    Returns:
        Tuple of (poisoned_images, poisoned_labels).
    """
    num_samples = images.shape[0]
    num_to_poison = max(1, int(num_samples * poison_ratio))
    _, c, h, w = images.shape

    indices = torch.randperm(num_samples)[:num_to_poison]
    poisoned_images = images.clone()
    poisoned_labels = labels.clone()

    for idx in indices:
        # Determine trigger position
        if trigger_position == "bottom_right":
            y_start = h - trigger_size
            x_start = w - trigger_size
        elif trigger_position == "top_left":
            y_start = 0
            x_start = 0
        elif trigger_position == "center":
            y_start = (h - trigger_size) // 2
            x_start = (w - trigger_size) // 2
        elif trigger_position == "random":
            y_start = int(torch.randint(0, max(1, h - trigger_size), (1,)).item())
            x_start = int(torch.randint(0, max(1, w - trigger_size), (1,)).item())
        else:
            raise ValueError(
                f"Unknown trigger_position: {trigger_position!r}. "
                f"Expected 'bottom_right', 'top_left', 'center', or 'random'."
            )

        y_end = min(y_start + trigger_size, h)
        x_end = min(x_start + trigger_size, w)

        # Apply trigger pattern
        if trigger_pattern == "square":
            poisoned_images[idx, :, y_start:y_end, x_start:x_end] = trigger_value
        elif trigger_pattern == "cross":
            # Draw an X pattern within the trigger region
            for dy in range(y_end - y_start):
                for dx in range(x_end - x_start):
                    # Diagonal lines of the X
                    ts = trigger_size - 1 if trigger_size > 1 else 1
                    if abs(dy - dx) <= 0 or abs(dy - (ts - dx)) <= 0:
                        poisoned_images[idx, :, y_start + dy, x_start + dx] = trigger_value
        else:
            raise ValueError(
                f"Unknown trigger_pattern: {trigger_pattern!r}. Expected 'square' or 'cross'."
            )

        poisoned_labels[idx] = target_class

    logging.debug(
        f"Backdoor trigger applied: {num_to_poison}/{num_samples} images, "
        f"pattern={trigger_pattern}, target_class={target_class}"
    )
    return poisoned_images, poisoned_labels


# ---------------------------------------------------------------------------
# Token replacement helpers (unchanged)
# ---------------------------------------------------------------------------


def _encode_vocabulary_sequences(tokenizer, vocabulary: list) -> dict:
    """Encode vocabulary words into token ID sequences, returning tuple-to-word mapping."""
    vocab_sequences = {}
    single_token_count = 0
    multi_token_count = 0

    for word in vocabulary:
        token_ids = tokenizer.encode(word, add_special_tokens=False)
        if token_ids:
            key = tuple(token_ids)
            vocab_sequences[key] = word

            if len(token_ids) == 1:
                single_token_count += 1
            else:
                multi_token_count += 1

    logging.info(
        f"Encoded {len(vocab_sequences)} vocabulary words: "
        f"{single_token_count} single-token, {multi_token_count} multi-token"
    )

    return vocab_sequences


def _apply_sequence_replacement(
    tokens: torch.Tensor,
    replacement_prob: float,
    target_sequences: dict,
    replacement_token_ids: list,
) -> torch.Tensor:
    """Replace multi-token sequences matching target vocabulary with random replacement tokens."""
    modified_tokens = tokens.clone()
    max_seq_length = max(len(seq) for seq in target_sequences)

    total_replacements = 0
    total_matches = 0

    for batch_idx in range(tokens.shape[0]):
        seq_idx = 0

        while seq_idx < tokens.shape[1]:
            matched = False

            for length in range(max_seq_length, 0, -1):
                if seq_idx + length > tokens.shape[1]:
                    continue

                window = tuple(tokens[batch_idx, seq_idx : seq_idx + length].tolist())

                if window in target_sequences:
                    total_matches += 1

                    if torch.rand(1).item() < replacement_prob:
                        replacement_id = replacement_token_ids[
                            int(torch.randint(0, len(replacement_token_ids), (1,)).item())
                        ]

                        modified_tokens[batch_idx, seq_idx] = replacement_id

                        if length > 1:
                            remaining_len = tokens.shape[1] - (seq_idx + length)
                            if remaining_len > 0:
                                modified_tokens[
                                    batch_idx,
                                    seq_idx + 1 : seq_idx + 1 + remaining_len,
                                ] = tokens[
                                    batch_idx,
                                    seq_idx + length : seq_idx + length + remaining_len,
                                ]
                            modified_tokens[batch_idx, -(length - 1) :] = 0
                        total_replacements += 1
                    matched = True
                    seq_idx += 1
                    break

            if not matched:
                seq_idx += 1

    if total_matches > 0:
        replacement_rate = total_replacements / total_matches * 100
        logging.debug(
            f"Token replacement: {total_replacements}/{total_matches} matches replaced "
            f"({replacement_rate:.1f}%)"
        )

    return modified_tokens


def _apply_single_token_replacement(
    tokens: torch.Tensor,
    replacement_prob: float,
    target_token_ids: list,
    replacement_token_ids: list,
) -> torch.Tensor:
    """Replace individual target tokens with random replacement tokens based on probability."""
    modified_tokens = tokens.clone()

    for batch_idx in range(tokens.shape[0]):
        for seq_idx in range(tokens.shape[1]):
            token_id = tokens[batch_idx, seq_idx].item()

            if token_id in target_token_ids and torch.rand(1).item() < replacement_prob:
                replacement_id = replacement_token_ids[
                    int(torch.randint(0, len(replacement_token_ids), (1,)).item())
                ]
                modified_tokens[batch_idx, seq_idx] = replacement_id

    return modified_tokens


def apply_token_replacement(
    tokens: torch.Tensor,
    replacement_prob: float = 0.2,
    target_token_ids: list | None = None,
    replacement_token_ids: list | None = None,
    target_sequences: dict | None = None,
) -> torch.Tensor:
    """Apply token replacement attack with single-token or multi-token sequence matching.

    Args:
        tokens: Input token tensor of shape (N, seq_len).
        replacement_prob: Probability of replacing each match. Defaults to 0.2.
        target_token_ids: List of single token IDs to target.
        replacement_token_ids: List of token IDs to use as replacements.
        target_sequences: Dict mapping token ID tuples to words for sequence matching.

    Returns:
        Modified token tensor with replacements applied, or original if no targets specified.
    """
    if replacement_prob <= 0:
        return tokens

    if not replacement_token_ids:
        return tokens

    if target_sequences:
        return _apply_sequence_replacement(
            tokens, replacement_prob, target_sequences, replacement_token_ids
        )
    elif target_token_ids:
        return _apply_single_token_replacement(
            tokens, replacement_prob, target_token_ids, replacement_token_ids
        )
    else:
        return tokens


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


def should_poison_this_round(
    current_round: int, client_id: int, attack_schedule: list | None
) -> tuple[bool, list]:
    """Determine if a client should be poisoned this round based on attack schedule.

    Args:
        current_round: Current training round number.
        client_id: ID of the client to check.
        attack_schedule: List of attack configuration dicts with round ranges and client targeting.

    Returns:
        Tuple of (should_poison, active_attacks) where active_attacks is a list of
        matching attack configs for this client and round.
    """
    if not attack_schedule:
        return False, []

    attacks_by_type = {}

    for attack_entry in attack_schedule:
        start_round = attack_entry.get("start_round", 1)
        end_round = attack_entry.get("end_round", float("inf"))

        if not (start_round <= current_round <= end_round):
            continue

        selection_strategy = attack_entry.get("selection_strategy", "specific")
        is_match = False

        if selection_strategy == "specific":
            malicious_client_ids = attack_entry.get("malicious_client_ids", [])
            if client_id in malicious_client_ids:
                is_match = True

        elif selection_strategy == "random" or selection_strategy == "percentage":
            targeted_clients = attack_entry.get("_selected_clients", [])
            if client_id in targeted_clients:
                is_match = True

        if is_match:
            attack_type = attack_entry.get("attack_type")
            if attack_type and attack_type not in attacks_by_type:
                attacks_by_type[attack_type] = attack_entry

    return len(attacks_by_type) > 0, list(attacks_by_type.values())


# ---------------------------------------------------------------------------
# Dispatch wrappers -- thin adapters between config dicts and pure functions
# ---------------------------------------------------------------------------


def _dispatch_label_flipping(
    data: torch.Tensor,
    labels: torch.Tensor,
    config: dict,
    tokenizer=None,
    num_classes: int | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    if num_classes is None:
        raise ValueError("Label flipping attack requires 'num_classes' parameter to be provided.")
    labels = apply_label_flipping(labels, num_classes=num_classes)
    return data, labels


def _dispatch_targeted_label_flipping(
    data: torch.Tensor,
    labels: torch.Tensor,
    config: dict,
    tokenizer=None,
    num_classes: int | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    source_class = config.get("source_class")
    target_class = config.get("target_class")
    if source_class is None or target_class is None:
        raise ValueError(
            "Targeted label flipping requires 'source_class' and 'target_class' in config."
        )
    labels = apply_targeted_label_flipping(
        labels,
        source_class=source_class,
        target_class=target_class,
        flip_ratio=config.get("flip_ratio", 1.0),
    )
    return data, labels


def _dispatch_gaussian_noise(
    data: torch.Tensor,
    labels: torch.Tensor,
    config: dict,
    tokenizer=None,
    num_classes: int | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    target_noise_snr = config.get("target_noise_snr")
    attack_ratio = config.get("attack_ratio", 1.0)

    if target_noise_snr is not None:
        data = apply_gaussian_noise(
            data, target_noise_snr=target_noise_snr, attack_ratio=attack_ratio
        )
    else:
        data = apply_gaussian_noise(
            data,
            mean=config.get("mean", 0.0),
            std=config.get("std", 0.1),
            attack_ratio=attack_ratio,
        )
    return data, labels


def _dispatch_token_replacement(
    data: torch.Tensor,
    labels: torch.Tensor,
    config: dict,
    tokenizer=None,
    num_classes: int | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    target_token_ids = config.get("target_token_ids")
    replacement_token_ids = config.get("replacement_token_ids")
    target_sequences = None

    if tokenizer and not target_token_ids:
        if "target_vocabulary" not in config:
            raise ValueError(
                "Token replacement attack requires 'target_vocabulary' in attack_config. "
                "Use predefined vocabularies from token_vocabularies.py (e.g., 'medical', "
                "'financial', 'legal')."
                "See intellifl/attack_utils/token_vocabularies.py for available vocabularies."
            )

        vocab_name: str = config["target_vocabulary"]
        strategy_name = config.get("replacement_strategy", "negative")

        target_tokens = get_vocabulary(vocab_name)
        replacement_tokens = get_replacement_strategy(strategy_name)

        logging.info(f"Using vocabulary '{vocab_name}' with '{strategy_name}' replacement strategy")
        logging.info(
            f"Loaded {len(target_tokens)} target tokens, {len(replacement_tokens)} replacement tokens"
        )

        if target_tokens and replacement_tokens:
            target_sequences = _encode_vocabulary_sequences(tokenizer, target_tokens)

            replacement_token_ids = [
                tokenizer.encode(token, add_special_tokens=False)[0]
                for token in replacement_tokens
                if tokenizer.encode(token, add_special_tokens=False)
            ]

            logging.info(
                f"Sequence replacement: {len(target_sequences)} target sequences, "
                f"{len(replacement_token_ids)} replacement IDs"
            )

    data = apply_token_replacement(
        data,
        replacement_prob=config.get("replacement_prob", config.get("replacement_probability", 0.2)),
        target_token_ids=target_token_ids,
        replacement_token_ids=replacement_token_ids,
        target_sequences=target_sequences,
    )
    return data, labels


def _dispatch_backdoor_trigger(
    data: torch.Tensor,
    labels: torch.Tensor,
    config: dict,
    tokenizer=None,
    num_classes: int | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    target_class = config.get("target_class")
    if target_class is None:
        raise ValueError("Backdoor trigger attack requires 'target_class' in config.")
    return apply_backdoor_trigger(
        data,
        labels,
        target_class=target_class,
        trigger_pattern=config.get("trigger_pattern", "square"),
        trigger_size=config.get("trigger_size", 4),
        trigger_position=config.get("trigger_position", "bottom_right"),
        trigger_value=config.get("trigger_value", 1.0),
        poison_ratio=config.get("poison_ratio", 0.1),
    )


# Registry mapping attack type names to dispatch functions
_DATA_ATTACK_FUNCTIONS: dict[str, Callable] = {
    "label_flipping": _dispatch_label_flipping,
    "targeted_label_flipping": _dispatch_targeted_label_flipping,
    "gaussian_noise": _dispatch_gaussian_noise,
    "token_replacement": _dispatch_token_replacement,
    "backdoor_trigger": _dispatch_backdoor_trigger,
}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def apply_poisoning_attack(
    data: torch.Tensor,
    labels: torch.Tensor,
    attack_config: dict,
    tokenizer=None,
    num_classes: int | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Apply a poisoning attack to dataset based on attack configuration.

    Supports label_flipping, targeted_label_flipping, gaussian_noise,
    token_replacement, and backdoor_trigger attack types.

    Args:
        data: Input data tensor (images or token IDs).
        labels: Input label tensor.
        attack_config: Attack configuration dict with 'attack_type' and type-specific params.
        tokenizer: HuggingFace tokenizer for token_replacement attacks.
        num_classes: Number of classes for label_flipping attacks.

    Returns:
        Tuple of (poisoned_data, poisoned_labels).

    Raises:
        ValueError: If old nested attack config format detected or required params missing.
    """
    if "params" in attack_config or (
        "type" in attack_config and "attack_type" not in attack_config
    ):
        raise ValueError(
            "Detected old nested attack config format. "
            "Please use flat attack_schedule format instead. "
            "Example: {'attack_type': 'label_flipping'} "
            "See docs/attack-scheduling.md guide."
        )

    attack_type = attack_config.get("attack_type")
    if not isinstance(attack_type, str):
        logging.warning(f"Invalid attack_type: {attack_type!r}, skipping.")
        return data, labels
    dispatch_fn = _DATA_ATTACK_FUNCTIONS.get(attack_type)

    if dispatch_fn is None:
        logging.warning(f"Unknown data attack type: {attack_type!r}, skipping.")
        return data, labels

    return dispatch_fn(data, labels, attack_config, tokenizer, num_classes)
