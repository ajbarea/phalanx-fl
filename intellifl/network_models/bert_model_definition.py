from __future__ import annotations

import contextlib
import io
from collections import OrderedDict

import torch

# -------------------------------
# Model Loading
# -------------------------------


def load_model_with_lora(
    model_name: str,
    lora_rank: int,
    lora_alpha: int,
    lora_dropout: float,
    lora_target_modules: list | None = None,
):
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForMaskedLM

    if lora_target_modules is None:
        lora_target_modules = ["query", "value"]
    model = AutoModelForMaskedLM.from_pretrained(model_name)
    lora_config = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        target_modules=lora_target_modules,
    )
    model = get_peft_model(model, lora_config)

    with io.StringIO() as buf, contextlib.redirect_stdout(buf):
        model.print_trainable_parameters()

    return model


def load_model(
    model_name: str,
):
    from transformers import AutoModelForMaskedLM

    model = AutoModelForMaskedLM.from_pretrained(model_name)

    return model


# -------------------------------
# State Dict (LoRA + Full)
# -------------------------------


def get_peft_model_state_dict(model):
    """Returns the state dict of LoRA adapter weights."""
    from peft import get_peft_model_state_dict as _get_peft_model_state_dict

    return _get_peft_model_state_dict(model)


def set_peft_model_state_dict(model, state_dict):
    """Sets the state dict of LoRA adapter weights."""
    from peft import set_peft_model_state_dict as _set_peft_model_state_dict

    return _set_peft_model_state_dict(model, state_dict)


def get_lora_state_dict(model):
    """
    Return LoRA adapter weights as a list of numpy arrays.
    """
    state_dict = get_peft_model_state_dict(model)
    return [val.cpu().numpy() for val in state_dict.values()]


def set_lora_state_dict(model, state_list):
    """
    Load LoRA adapter weights from a list of numpy arrays.
    """
    keys = get_peft_model_state_dict(model).keys()
    state_dict = OrderedDict({k: torch.tensor(v) for k, v in zip(keys, state_list, strict=False)})
    set_peft_model_state_dict(model, state_dict)
