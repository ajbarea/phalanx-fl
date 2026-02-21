from __future__ import annotations

import logging

from jsonschema import ValidationError, validate

config_schema = {
    "type": "object",
    "properties": {
        # Common parameters
        "aggregation_strategy_keyword": {
            "type": "string",
            "enum": [
                "trust",
                "pid",
                "pid_scaled",
                "pid_standardized",
                "pid_standardized_score_based",
                "multi-krum",
                "krum",
                "multi-krum-based",
                "trimmed_mean",
                "rfa",
                "bulyan",
                "fedavg",
                "arkrum",
            ],
        },
        "strict_mode": {"type": "boolean"},
        "remove_clients": {"type": "boolean"},
        "dataset_keyword": {
            "type": "string",
            "enum": [
                "femnist_iid",
                "femnist_niid",
                "its",
                "pneumoniamnist",
                "flair",
                "bloodmnist",
                "medquad",
                "financial_phrasebank",
                "lexglue",
                "lung_photos",
                "breastmnist",
                "pathmnist",
                "dermamnist",
                "octmnist",
                "retinamnist",
                "tissuemnist",
                "organamnist",
                "organcmnist",
                "organsmnist",
                "pubmed_classification_20k",
                "medal",
            ],
        },
        "model_type": {"type": "string", "enum": ["cnn", "transformer"]},
        "num_of_rounds": {"type": "integer"},
        "num_of_clients": {"type": "integer"},
        "show_plots": {"type": "boolean"},
        "save_plots": {"type": "boolean"},
        "save_csv": {"type": "boolean"},
        "preserve_dataset": {"type": "boolean"},
        "training_subset_fraction": {"type": "number"},
        # LLM settings
        "use_llm": {"type": "boolean"},
        "llm_model": {
            "type": "string",
            "enum": [
                "microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext",
                "distilbert-base-uncased",
            ],
        },
        "llm_task": {"type": "string", "enum": ["mlm"]},
        "mlm_probability": {"type": "number"},
        "llm_chunk_size": {"type": "integer"},
        "llm_finetuning": {"type": "string", "enum": ["full", "lora"]},
        "lora_rank": {"type": "integer"},
        "lora_alpha": {"type": "integer"},
        "lora_dropout": {"type": "number"},
        "lora_target_modules": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        # Flower settings
        "training_device": {"type": "string", "enum": ["cpu", "gpu"]},
        "cpus_per_client": {"type": "number"},
        "gpus_per_client": {"type": "number"},
        "min_fit_clients": {"type": "integer"},
        "min_evaluate_clients": {"type": "integer"},
        "min_available_clients": {"type": "integer"},
        "evaluate_metrics_aggregation_fn": {
            "type": "string",
        },
        "num_of_client_epochs": {"type": "integer"},
        "batch_size": {"type": "integer"},
        # Strategy specific parameters
        # Trust
        "begin_removing_from_round": {"type": "integer", "minimum": 1},
        # Client removal termination policies
        "termination_policy": {
            "type": "string",
            "enum": ["strict", "graceful", "adaptive"],
        },
        "min_clients_ratio": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "trust_threshold": {"type": "number"},
        "beta_value": {"type": "number"},
        "num_of_clusters": {"type": "integer", "minimum": 1, "maximum": 1},
        # PID, PID scaled, PID standardized
        "num_std_dev": {"type": "number"},
        "Kp": {"type": "number"},
        "Ki": {"type": "number"},
        "Kd": {"type": "number"},
        # Krum-based strategies
        "num_krum_selections": {"type": "integer"},
        # Trimmed mean
        "trim_ratio": {"type": "number"},
        # Attack scheduling
        "attack_schedule": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_round": {"type": "integer", "minimum": 1},
                    "end_round": {"type": "integer", "minimum": 1},
                    "attack_type": {
                        "type": "string",
                        "enum": [
                            "label_flipping",
                            "targeted_label_flipping",
                            "gaussian_noise",
                            "token_replacement",
                            "backdoor_trigger",
                            "model_poisoning",
                            "gradient_scaling",
                            "boosted_scaling",
                            "byzantine_perturbation",
                            "inner_product_manipulation",
                            "alternating_min_poisoning",
                        ],
                    },
                    "selection_strategy": {
                        "type": "string",
                        "enum": ["specific", "random", "percentage"],
                    },
                    "malicious_client_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "malicious_client_count": {"type": "integer", "minimum": 1},
                    "malicious_percentage": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                    "random_seed": {"type": "integer", "minimum": 0},
                    "target_noise_snr": {"type": "number"},
                    "attack_ratio": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    # Weight poisoning parameters
                    "poison_ratio": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "magnitude": {"type": "number", "minimum": 0.0},
                    "scale_factor": {"type": "number", "minimum": 0.0},
                    "noise_scale": {"type": "number", "minimum": 0.0},
                    "clip_norm": {"type": "number", "minimum": 0.0},
                    "seed": {"type": "integer", "minimum": 0},
                    # Boosted scaling parameters
                    "n_total": {"type": "integer", "minimum": 1},
                    "n_malicious": {"type": "integer", "minimum": 1},
                    "boost_factor": {"type": "number"},
                    # Inner product manipulation parameters
                    "perturbation_strength": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "target_direction": {
                        "type": "string",
                        "enum": ["negative", "zero", "random"],
                    },
                    # Targeted label flipping parameters
                    "source_class": {"type": "integer", "minimum": 0},
                    "target_class": {"type": "integer", "minimum": 0},
                    "flip_ratio": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    # Alternating-min poisoning (optimization-based) parameters
                    "tau_factor": {"type": "number", "minimum": 0.0},
                    "pgd_steps": {"type": "integer", "minimum": 1},
                    "pgd_step_size": {"type": "number", "exclusiveMinimum": 0.0, "maximum": 1.0},
                    # Backdoor trigger parameters
                    "trigger_pattern": {"type": "string", "enum": ["square", "cross"]},
                    "trigger_size": {"type": "integer", "minimum": 1},
                    "trigger_position": {
                        "type": "string",
                        "enum": ["bottom_right", "top_left", "center", "random"],
                    },
                    "trigger_value": {"type": "number"},
                    # Token replacement parameters
                    "target_vocabulary": {"type": "string"},
                    "replacement_strategy": {"type": "string"},
                    "replacement_prob": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                },
                "required": [
                    "start_round",
                    "end_round",
                    "attack_type",
                    "selection_strategy",
                ],
            },
        },
        # Attack snapshot saving
        "save_attack_snapshots": {"type": "boolean"},
        "attack_snapshot_format": {
            "type": "string",
            "enum": ["pickle", "visual", "pickle_and_visual"],
        },
        "snapshot_max_samples": {"type": "integer", "minimum": 1, "maximum": 50},
    },
    "required": [
        "aggregation_strategy_keyword",
        "remove_clients",
        "dataset_keyword",
        "model_type",
        "use_llm",
        "num_of_rounds",
        "num_of_clients",
        "show_plots",
        "save_plots",
        "save_csv",
        "preserve_dataset",
        "training_subset_fraction",
        "training_device",
        "cpus_per_client",
        "gpus_per_client",
        "min_fit_clients",
        "min_evaluate_clients",
        "min_available_clients",
        "evaluate_metrics_aggregation_fn",
        "num_of_client_epochs",
        "batch_size",
        "attack_schedule",
    ],
}


def _validate_dependent_params(strategy_config: dict) -> None:
    """Validate strategy-specific required parameters are present."""

    aggregation_strategy_keyword = strategy_config["aggregation_strategy_keyword"]

    if aggregation_strategy_keyword == "trust":
        trust_specific_parameters = [
            "begin_removing_from_round",
            "trust_threshold",
            "beta_value",
            "num_of_clusters",
        ]
        for param in trust_specific_parameters:
            if param not in strategy_config:
                raise ValidationError(
                    f"Missing parameter {param} for trust aggregation {aggregation_strategy_keyword}"
                )
    elif aggregation_strategy_keyword in (
        "pid",
        "pid_scaled",
        "pid_standardized",
        "pid_standardized_score_based",
    ):
        pid_specific_parameters = ["num_std_dev", "Kp", "Ki", "Kd"]
        for param in pid_specific_parameters:
            if param not in strategy_config:
                raise ValidationError(
                    f"Missing parameter {param} for PID aggregation {aggregation_strategy_keyword}"
                )
    elif aggregation_strategy_keyword in ["multi-krum", "krum", "multi-krum-based"]:
        if "num_krum_selections" not in strategy_config:
            raise ValidationError(
                f"Missing parameter num_krum_selections for Krum-based aggregation {aggregation_strategy_keyword}"
            )

        # SCIENTIFIC INTEGRITY: Krum requires n > 2f + 2
        # where n is num_of_clients and f is num_of_malicious_clients
        n = strategy_config.get("num_of_clients", 0)
        f = strategy_config.get("num_of_malicious_clients", 0)
        if n <= 2 * f + 2:
            raise ValidationError(
                f"CONFIG REJECTED: Krum aggregation requires n > 2f + 2\n"
                f"Current config: n={n}, f={f}\n"
                f"Requirement: {n} > {2 * f + 2}\n"
                f"Reference: 'Machine Learning with Adversaries: Byzantine Tolerant Gradient Descent' (NIPS 2017)"
            )

    elif aggregation_strategy_keyword == "trimmed_mean":
        if "trim_ratio" not in strategy_config:
            raise ValidationError(
                f"Missing parameter trim_ratio for trimmed mean aggregation {aggregation_strategy_keyword}"
            )

        # SCIENTIFIC INTEGRITY: Trim ratio must be < 0.5
        trim_ratio = strategy_config.get("trim_ratio", 0)
        if trim_ratio >= 0.5:
            raise ValidationError(
                f"CONFIG REJECTED: Trimmed Mean ratio must be < 0.5 (got {trim_ratio})\n"
                f"Reason: Trimming 50% or more from each side removes all data points."
            )


def _populate_client_selection(config: dict) -> None:
    """Populate _selected_clients for random and percentage selection strategies."""
    import random

    schedule = config.get("attack_schedule", [])
    num_of_clients = config.get("num_of_clients")
    if num_of_clients is None:
        return  # No clients configured, skip client selection

    for idx, entry in enumerate(schedule):
        selection_strategy = entry.get("selection_strategy")

        if selection_strategy == "specific":
            # Already has explicit malicious_client_ids, nothing to do
            continue

        elif selection_strategy in ("random", "percentage"):
            if "random_seed" in entry:
                seed = entry["random_seed"]
            else:
                # Auto-generate seed from attack parameters for reproducibility
                seed_string = f"{entry.get('attack_type')}_{entry.get('start_round')}_{entry.get('end_round')}_{idx}"
                seed = hash(seed_string) % (2**32)

            random.seed(seed)

            if selection_strategy == "random":
                num_malicious = entry.get("malicious_client_count")
            else:
                malicious_percentage = entry.get("malicious_percentage")
                num_malicious = int(num_of_clients * malicious_percentage)

            if num_malicious > num_of_clients:
                raise ValidationError(
                    f"attack_schedule entry {idx}: Cannot select {num_malicious} clients "
                    f"when only {num_of_clients} clients exist"
                )

            if num_malicious <= 0:
                raise ValidationError(
                    f"attack_schedule entry {idx}: Must select at least 1 malicious client "
                    f"(got {num_malicious})"
                )

            all_client_ids = list(range(num_of_clients))
            selected_clients = sorted(random.sample(all_client_ids, num_malicious))

            entry["_selected_clients"] = selected_clients

            logging.debug(
                f"attack_schedule entry {idx} ({selection_strategy}): "
                f"Selected clients {selected_clients} for {entry.get('attack_type')} attack "
                f"(seed={seed})"
            )


def _validate_attack_schedule(config: dict) -> None:
    """Validate attack_schedule entries and enforce related constraints."""
    schedule = config.get("attack_schedule", [])

    for idx, entry in enumerate(schedule):
        entry_desc = f"attack_schedule entry {idx}"

        # Validate round range
        start_round = entry.get("start_round")
        end_round = entry.get("end_round")
        if start_round > end_round:
            raise ValidationError(
                f"{entry_desc}: start_round ({start_round}) cannot be greater than end_round ({end_round})"
            )

        # Validate attack type and its required parameters
        num_of_rounds = config.get("num_of_rounds")
        if end_round > num_of_rounds:
            raise ValidationError(
                f"{entry_desc}: end_round ({end_round}) exceeds num_of_rounds ({num_of_rounds})"
            )

        attack_type = entry.get("attack_type")

        if attack_type == "gaussian_noise":
            if "target_noise_snr" not in entry:
                raise ValidationError(
                    f"{entry_desc}: gaussian_noise attack requires 'target_noise_snr' parameter"
                )
            if "attack_ratio" not in entry:
                raise ValidationError(
                    f"{entry_desc}: gaussian_noise attack requires 'attack_ratio' parameter"
                )

        elif attack_type == "targeted_label_flipping":
            if "source_class" not in entry:
                raise ValidationError(
                    f"{entry_desc}: targeted_label_flipping requires 'source_class' parameter"
                )
            if "target_class" not in entry:
                raise ValidationError(
                    f"{entry_desc}: targeted_label_flipping requires 'target_class' parameter"
                )

        elif attack_type == "backdoor_trigger":
            if "target_class" not in entry:
                raise ValidationError(
                    f"{entry_desc}: backdoor_trigger requires 'target_class' parameter"
                )

        elif attack_type == "boosted_scaling":
            if "n_total" not in entry:
                raise ValidationError(f"{entry_desc}: boosted_scaling requires 'n_total' parameter")

        elif attack_type == "alternating_min_poisoning":
            if "n_total" not in entry:
                raise ValidationError(
                    f"{entry_desc}: alternating_min_poisoning requires 'n_total' parameter"
                )

        # Validate selection strategy requirements
        selection_strategy = entry.get("selection_strategy")

        if selection_strategy == "specific":
            if "malicious_client_ids" not in entry:
                raise ValidationError(
                    f"{entry_desc}: 'specific' selection strategy requires 'malicious_client_ids' list"
                )

        elif selection_strategy == "random":
            if "malicious_client_count" not in entry:
                raise ValidationError(
                    f"{entry_desc}: 'random' selection strategy requires 'malicious_client_count' integer"
                )

        elif selection_strategy == "percentage":
            if "malicious_percentage" not in entry:
                raise ValidationError(
                    f"{entry_desc}: 'percentage' selection strategy requires 'malicious_percentage' (0.0-1.0)"
                )

    # Check for overlapping rounds (attack stacking)
    for i, entry1 in enumerate(schedule):
        for j, entry2 in enumerate(schedule[i + 1 :], start=i + 1):
            if not (
                entry1["end_round"] < entry2["start_round"]
                or entry2["end_round"] < entry1["start_round"]
            ):
                # Check if same attack type
                if entry1.get("attack_type") == entry2.get("attack_type"):
                    raise ValidationError(
                        f"CONFIG REJECTED: Overlapping rounds with same attack type\n"
                        f"\n"
                        f"Conflict:\n"
                        f"  - Entry {i}: {entry1.get('attack_type')} (rounds {entry1['start_round']}-{entry1['end_round']})\n"
                        f"  - Entry {j}: {entry2.get('attack_type')} (rounds {entry2['start_round']}-{entry2['end_round']})\n"
                        f"\n"
                        f"Reason:\n"
                        f"  - Cannot have the same attack type active in overlapping rounds\n"
                        f"  - Config is the single source of truth - it must be unambiguous\n"
                        f"\n"
                        f"Fix:\n"
                        f"  - Adjust round ranges to not overlap for same attack type\n"
                        f"  - Or use different attack types if you want stacked attacks\n"
                    )
                else:
                    logging.info(
                        f"attack_schedule entries {i} and {j} have overlapping rounds with different attack types "
                        f"({entry1.get('attack_type')} and {entry2.get('attack_type')}). "
                        f"Both attacks will be stacked and applied sequentially."
                    )

    # Strict rejection: preserve_dataset incompatible with attack_schedule
    preserve_dataset = config.get("preserve_dataset")
    if schedule and preserve_dataset is True:
        raise ValidationError(
            "CONFIG REJECTED: Cannot use attack_schedule with preserve_dataset=true\n"
            "\n"
            "Reason:\n"
            "  - attack_schedule applies attacks in-memory during training rounds\n"
            "  - preserve_dataset=true expects pre-poisoned filesystem dataset\n"
            "  - These modes are incompatible\n"
            "\n"
            "Fix:\n"
            "  Set 'preserve_dataset': false in your config file\n"
            "  Use 'save_attack_snapshots': true to inspect poisoned data\n"
            "\n"
            "Config is the single source of truth - it must reflect intended execution."
        )


def _validate_llm_parameters(strategy_config: dict) -> None:
    """Validate LLM-specific parameters are present and valid."""

    if strategy_config["model_type"] != "transformer":
        raise ValidationError("LLM finetuning is only supported for transformer models")

    llm_specific_parameters = [
        "llm_model",
        "llm_finetuning",
        "llm_task",
        "llm_chunk_size",
    ]
    for param in llm_specific_parameters:
        if param not in strategy_config:
            raise ValidationError(f"Missing parameter {param} for LLM finetuning")

    if strategy_config["llm_task"] == "mlm" and "mlm_probability" not in strategy_config:
        raise ValidationError("Missing parameter mlm_probability for LLM task mlm")

    finetuning_keyword = strategy_config["llm_finetuning"]
    if finetuning_keyword == "lora":
        lora_specific_parameters = [
            "lora_rank",
            "lora_alpha",
            "lora_dropout",
            "lora_target_modules",
        ]
        for param in lora_specific_parameters:
            if param not in strategy_config:
                raise ValidationError(f"Missing parameter {param} for LORA")


def _apply_strict_mode(config: dict) -> None:
    """Handle strict_mode validation and client configuration logic."""

    # Set strict_mode to True by default if not specified
    if "strict_mode" not in config:
        config["strict_mode"] = True

    strict_mode = config["strict_mode"] is True
    num_of_clients = config["num_of_clients"]
    num_fit_clients = config["min_fit_clients"]
    num_evaluate_clients = config["min_evaluate_clients"]
    num_available_clients = config["min_available_clients"]

    # Always check: min_* cannot be greater than num_of_clients
    if (
        num_fit_clients > num_of_clients
        or num_evaluate_clients > num_of_clients
        or num_available_clients > num_of_clients
    ):
        raise ValidationError(
            f"EXPERIMENT STOPPED: Client configuration error.\n"
            f"Cannot require more clients than available:\n"
            f"  - Total clients: {num_of_clients}\n"
            f"  - min_fit_clients: {num_fit_clients}\n"
            f"  - min_evaluate_clients: {num_evaluate_clients}\n"
            f"  - min_available_clients: {num_available_clients}\n"
            f"Please ensure all min_* values are <= {num_of_clients}"
        )

    # If strict_mode is enabled, reject configs where min_* != num_of_clients
    if strict_mode and (
        num_fit_clients != num_of_clients
        or num_evaluate_clients != num_of_clients
        or num_available_clients != num_of_clients
    ):
        raise ValidationError(
            f"CONFIG REJECTED: strict_mode requires all clients to participate.\n"
            f"\n"
            f"Current values:\n"
            f"  - num_of_clients: {num_of_clients}\n"
            f"  - min_fit_clients: {num_fit_clients}\n"
            f"  - min_evaluate_clients: {num_evaluate_clients}\n"
            f"  - min_available_clients: {num_available_clients}\n"
            f"\n"
            f"Fix:\n"
            f"  Set all min_* values equal to num_of_clients ({num_of_clients})\n"
            f"  Or set 'strict_mode': 'false' to allow partial participation\n"
        )


def validate_removal_configuration(config: dict) -> tuple[dict, list[str]]:
    """
    Validate client removal configuration for consistency and conflicts.

    Byzantine-robust federated learning requires careful handling of client removal
    to maintain minimum federation size for meaningful aggregation.
    References:
    - Byzantine-Robust FL (arXiv 2024): https://arxiv.org/abs/2402.12780
    - Centralized FL Security (SpringerLink 2022): https://link.springer.com/chapter/10.1007/978-3-032-03705-3_10

    Args:
        config: Configuration dictionary to validate.

    Returns:
        (config, warnings): Validated config and list of warning messages.
    """
    warnings: list[str] = []
    modified_config = config.copy()

    if not config.get("remove_clients", False):
        return modified_config, warnings  # No removal, no issues

    num_clients = config["num_of_clients"]
    min_fit = config.get("min_fit_clients", num_clients)
    begin_removing = config.get("begin_removing_from_round", 1)
    num_rounds = config["num_of_rounds"]
    termination_policy = config.get("termination_policy", "graceful")

    # Check: begin_removing_from_round is before last round
    if begin_removing >= num_rounds:
        warnings.append(
            f"begin_removing_from_round ({begin_removing}) >= num_of_rounds "
            f"({num_rounds}). Removal will never trigger."
        )

    # Check: min_fit_clients feasible with removal
    if termination_policy == "strict" and min_fit == num_clients:
        warnings.append(
            "STRICT termination + min_fit_clients == num_of_clients "
            "means any removal will terminate experiment. "
            "Consider 'graceful' or 'adaptive' policy."
        )

    # STRICT REJECTION: strict_mode incompatible with removal
    # Strict mode enforces min_fit_clients == num_of_clients, which conflicts
    # with client removal (impossible to satisfy both constraints)
    # Research: Byzantine-robust FL (arXiv 2024): https://arxiv.org/abs/2402.12780
    if config.get("strict_mode", True):
        raise ValidationError(
            "CONFIG REJECTED: strict_mode=true is incompatible with remove_clients=true\n"
            "\n"
            "Reason:\n"
            "  - strict_mode enforces min_fit_clients == num_of_clients (100% participation)\n"
            "  - remove_clients=true enables permanent removal of clients during the experiment\n"
            "  - It is mathematically impossible to maintain 100% participation while removing clients\n"
            "\n"
            "Fix:\n"
            "  - Set 'strict_mode': false in your configuration\n"
            "  - This allows the experiment to continue as long as the Federation size \n"
            "    satisfies the chosen 'termination_policy' and aggregation constraints.\n"
            "\n"
            "Reference: https://arxiv.org/abs/2402.12780 (Byzantine-Robust FL)"
        )

    return modified_config, warnings


def validate_strategy_config(config: dict) -> None:
    """Validate simulation config against schema and strategy-specific constraints.

    Args:
        config: Configuration dictionary to validate and populate.

    Raises:
        ValidationError: If config fails schema or constraint validation.
    """

    # Validates config structure, types, and basic constraints against JSON schema
    validate(instance=config, schema=config_schema)

    # Validate removal configuration conflicts
    config_corrected, removal_warnings = validate_removal_configuration(config)
    config.update(config_corrected)
    if removal_warnings:
        logging.warning("Client Removal Configuration Warnings:")
        for warning in removal_warnings:
            logging.warning(f"  - {warning}")

    _validate_dependent_params(config)

    if config["use_llm"] is True:
        _validate_llm_parameters(config)

    _validate_attack_schedule(config)
    _populate_client_selection(config)
    _apply_strict_mode(config)
