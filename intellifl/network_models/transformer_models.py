from __future__ import annotations

import contextlib
import io
from collections import OrderedDict

# -----------------------------------------------
# Unified Model Loading
# -----------------------------------------------
from dataclasses import dataclass

import torch


@dataclass(frozen=True)
class _TaskConfig:
    auto_class: str
    lora_target_modules: list[str]
    lora_task_type: str | None


_TASK_DEFAULTS: dict[str, _TaskConfig] = {
    "mlm": _TaskConfig(
        auto_class="AutoModelForMaskedLM",
        lora_target_modules=["query", "value"],
        lora_task_type=None,
    ),
    "seq_cls": _TaskConfig(
        auto_class="AutoModelForSequenceClassification",
        lora_target_modules=["q_lin", "v_lin"],
        lora_task_type="SEQ_CLS",
    ),
}


def load_hf_model(
    model_name: str,
    task: str,
    num_labels: int | None = None,
    use_lora: bool = False,
    lora_rank: int = 8,
    lora_alpha: int = 16,
    lora_dropout: float = 0.1,
    lora_target_modules: list | None = None,
):
    """
    Load a HuggingFace transformer model for the given task.

    Args:
        model_name: HuggingFace model identifier (e.g., 'bert-base-uncased')
        task: 'mlm' (masked language modeling) or 'seq_cls' (sequence classification)
        num_labels: Number of classification labels (required for seq_cls)
        use_lora: Whether to apply LoRA adapters
        lora_rank: LoRA rank (r), controls adapter capacity
        lora_alpha: LoRA scaling parameter
        lora_dropout: Dropout probability for LoRA layers
        lora_target_modules: Module names to apply LoRA to (uses task-appropriate defaults)

    Returns:
        HuggingFace model, optionally wrapped with LoRA adapters
    """
    if task not in _TASK_DEFAULTS:
        raise ValueError(f"Unknown task: {task!r}. Must be one of {list(_TASK_DEFAULTS)}")

    defaults = _TASK_DEFAULTS[task]

    if task == "seq_cls" and num_labels is None:
        raise ValueError("num_labels is required for task='seq_cls'")

    if use_lora:
        return _load_with_lora(
            model_name=model_name,
            auto_class_name=defaults.auto_class,
            num_labels=num_labels,
            lora_rank=lora_rank,
            lora_alpha=lora_alpha,
            lora_dropout=lora_dropout,
            lora_target_modules=lora_target_modules or defaults.lora_target_modules,
            lora_task_type=defaults.lora_task_type,
        )
    else:
        return _load_without_lora(
            model_name=model_name,
            auto_class_name=defaults.auto_class,
            num_labels=num_labels,
        )


# -----------------------------------------------
# Task-Specific Loaders (kept for backward compat)
# -----------------------------------------------


def load_model_with_lora(
    model_name: str,
    lora_rank: int,
    lora_alpha: int,
    lora_dropout: float,
    lora_target_modules: list | None = None,
):
    return load_hf_model(
        model_name,
        "mlm",
        use_lora=True,
        lora_rank=lora_rank,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        lora_target_modules=lora_target_modules,
    )


def load_model(model_name: str):
    return load_hf_model(model_name, "mlm")


def load_text_classifier_with_lora(
    model_name: str,
    num_labels: int,
    lora_rank: int = 8,
    lora_alpha: int = 16,
    lora_dropout: float = 0.1,
    lora_target_modules: list | None = None,
):
    return load_hf_model(
        model_name,
        "seq_cls",
        num_labels=num_labels,
        use_lora=True,
        lora_rank=lora_rank,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        lora_target_modules=lora_target_modules,
    )


def load_text_classifier_without_lora(model_name: str, num_labels: int):
    return load_hf_model(model_name, "seq_cls", num_labels=num_labels)


# -----------------------------------------------
# Internal Helpers
# -----------------------------------------------


def _load_with_lora(
    model_name: str,
    auto_class_name: str,
    num_labels: int | None,
    lora_rank: int,
    lora_alpha: int,
    lora_dropout: float,
    lora_target_modules: list[str],
    lora_task_type: str | None,
):
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForMaskedLM, AutoModelForSequenceClassification

    auto_class = (
        AutoModelForMaskedLM
        if auto_class_name == "AutoModelForMaskedLM"
        else AutoModelForSequenceClassification
    )

    pretrained_kwargs = {}
    if num_labels is not None:
        pretrained_kwargs["num_labels"] = num_labels
    model = auto_class.from_pretrained(model_name, **pretrained_kwargs)

    lora_kwargs: dict = {
        "r": lora_rank,
        "lora_alpha": lora_alpha,
        "lora_dropout": lora_dropout,
        "target_modules": lora_target_modules,
    }
    if lora_task_type is not None:
        lora_kwargs["task_type"] = lora_task_type

    model = get_peft_model(model, LoraConfig(**lora_kwargs))

    with io.StringIO() as buf, contextlib.redirect_stdout(buf):
        model.print_trainable_parameters()

    return model


def _load_without_lora(
    model_name: str,
    auto_class_name: str,
    num_labels: int | None,
):
    from transformers import AutoModelForMaskedLM, AutoModelForSequenceClassification

    auto_class = (
        AutoModelForMaskedLM
        if auto_class_name == "AutoModelForMaskedLM"
        else AutoModelForSequenceClassification
    )

    pretrained_kwargs = {}
    if num_labels is not None:
        pretrained_kwargs["num_labels"] = num_labels
    return auto_class.from_pretrained(model_name, **pretrained_kwargs)


# -----------------------------------------------
# LoRA State Dict Helpers (single copy)
# -----------------------------------------------


def get_peft_model_state_dict(model):
    """Returns the state dict of LoRA adapter weights."""
    from peft import get_peft_model_state_dict as _get_peft_model_state_dict

    return _get_peft_model_state_dict(model)


def set_peft_model_state_dict(model, state_dict):
    """Sets the state dict of LoRA adapter weights."""
    from peft import set_peft_model_state_dict as _set_peft_model_state_dict

    return _set_peft_model_state_dict(model, state_dict)


def get_lora_state_dict(model):
    """Return LoRA adapter weights as a list of numpy arrays."""
    state_dict = get_peft_model_state_dict(model)
    return [val.cpu().numpy() for val in state_dict.values()]


def set_lora_state_dict(model, state_list):
    """Load LoRA adapter weights from a list of numpy arrays."""
    keys = get_peft_model_state_dict(model).keys()
    state_dict = OrderedDict({k: torch.tensor(v) for k, v in zip(keys, state_list, strict=False)})
    set_peft_model_state_dict(model, state_dict)
