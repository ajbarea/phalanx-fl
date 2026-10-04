"""phalanx-fl ClientApp: local LoRA train/eval, adapter-only, OTel-traced.

Each client loads the broadcast adapter weights into a frozen-backbone LoRA model,
trains/evaluates on its non-IID partition, and replies with the updated adapters only.
A client span wraps each local pass so per-partition work shows up in traces.

Partitions listed in ``malicious-partitions`` poison their training labels from
``attack-start-round`` on and may scale their update by ``boost`` before replying.
Each reply carries a ``malicious`` flag for the server's bookkeeping only; no
aggregation rule reads it.
"""

from __future__ import annotations

import warnings
from typing import Any

import torch
from flwr.app import ArrayRecord, Context, Message, MetricRecord, RecordDict
from flwr.clientapp import ClientApp
from transformers import logging as hf_logging

from phalanx.task import (
    Flip,
    client_entropy,
    default_device,
    get_adapter_state,
    get_model,
    load_data,
    sample_count,
    set_adapter_state,
    set_seed,
    test_fn,
    train_fn,
)
from phalanx.telemetry import (
    client_span,
    context_from_traceparent,
    init_telemetry,
    record_client_metrics,
)

warnings.filterwarnings("ignore", category=FutureWarning)
hf_logging.set_verbosity_error()

app = ClientApp()


def _config(msg: Message) -> Any:
    return msg.content.config_records.get("config")


def _server_round(msg: Message) -> int:
    config = _config(msg)
    return int(config["server-round"]) if config and "server-round" in config else 0


def _parent_context(msg: Message) -> Any:
    """The server round span's context, if the round broadcast a traceparent."""
    config = _config(msg)
    if config and "traceparent" in config:
        return context_from_traceparent(str(config["traceparent"]))
    return None


def _data_kwargs(cfg: Any) -> dict[str, Any]:
    """The ``load_data`` keyword arguments shared by train and evaluate."""
    return {
        "dataset": str(cfg["dataset"]),
        "text_column": str(cfg["text-column"]),
        "partitioner": str(cfg["partitioner"]),
        "alpha": float(cfg["dirichlet-alpha"]),
        "seed": int(cfg["seed"]),
    }


def is_malicious(cfg: Any, partition_id: int) -> bool:
    """Whether ``partition_id`` is listed in the comma-separated ``malicious-partitions``."""
    listed = str(cfg["malicious-partitions"]).replace(" ", "")
    return str(partition_id) in listed.split(",") if listed else False


def attack_for(cfg: Any, partition_id: int, rnd: int) -> tuple[Flip | None, float]:
    """This client's (label flip, update boost) for ``rnd``; (None, 1.0) when honest."""
    if not is_malicious(cfg, partition_id) or rnd < int(cfg["attack-start-round"]):
        return None, 1.0
    flip = (int(cfg["flip-from"]), int(cfg["flip-to"])) if cfg["attack"] == "label-flip" else None
    return flip, float(cfg["boost"])


def boost_update(
    global_state: dict[str, torch.Tensor], local_state: dict[str, torch.Tensor], boost: float
) -> dict[str, torch.Tensor]:
    """Scale the update away from the global model: ``g + boost * (l - g)``."""
    return {k: global_state[k] + boost * (local_state[k] - global_state[k]) for k in local_state}


@app.train()
def train(msg: Message, context: Context) -> Message:
    """Load broadcast adapters, train locally, reply with updated adapters only."""
    # flwr config values are a broad union (bool/int/float/str/bytes); read as Any.
    cfg: Any = context.run_config
    node: Any = context.node_config
    init_telemetry(service_name=str(cfg["otel-service-name"]))
    partition_id = int(node["partition-id"])
    num_partitions = int(node["num-partitions"])
    rnd = _server_round(msg)
    set_seed(client_entropy(rnd, partition_id, int(cfg["seed"])))
    flip, boost = attack_for(cfg, partition_id, rnd)

    with client_span(
        rnd=rnd, partition_id=partition_id, phase="train", parent=_parent_context(msg)
    ):
        trainloader, _ = load_data(
            partition_id, num_partitions, str(cfg["model-name"]), flip=flip, **_data_kwargs(cfg)
        )
        model = get_model(
            str(cfg["model-name"]),
            num_labels=int(cfg["num-labels"]),
            target_modules=str(cfg["lora-target-modules"]),
        )
        global_state = msg.content.array_records["arrays"].to_torch_state_dict()
        # set_adapter_state mutates its argument; keep an untouched copy for boosting.
        set_adapter_state(model, {k: v.clone() for k, v in global_state.items()})
        device = default_device()
        model.to(device)
        loss = train_fn(
            model,
            trainloader,
            epochs=int(cfg["local-epochs"]),
            device=device,
            lr=float(cfg["learning-rate"]),
        )
        record_client_metrics(
            partition_id=partition_id, num_examples=sample_count(trainloader), loss=loss
        )

    state = {k: v.cpu() for k, v in get_adapter_state(model).items()}
    if boost != 1.0:
        state = boost_update(global_state, state, boost)
    content = RecordDict(
        {
            "arrays": ArrayRecord(state),
            "metrics": MetricRecord(
                {
                    "num-examples": sample_count(trainloader),
                    "train_loss": loss,
                    "malicious": int(is_malicious(cfg, partition_id)),
                }
            ),
        }
    )
    return Message(content=content, reply_to=msg)


@app.evaluate()
def evaluate(msg: Message, context: Context) -> Message:
    """Evaluate the broadcast adapters on this client's local test partition."""
    cfg: Any = context.run_config
    node: Any = context.node_config
    init_telemetry(service_name=str(cfg["otel-service-name"]))
    partition_id = int(node["partition-id"])
    num_partitions = int(node["num-partitions"])
    rnd = _server_round(msg)
    set_seed(client_entropy(rnd, partition_id, int(cfg["seed"])))

    with client_span(
        rnd=rnd, partition_id=partition_id, phase="evaluate", parent=_parent_context(msg)
    ):
        _, testloader = load_data(
            partition_id, num_partitions, str(cfg["model-name"]), **_data_kwargs(cfg)
        )
        model = get_model(
            str(cfg["model-name"]),
            num_labels=int(cfg["num-labels"]),
            target_modules=str(cfg["lora-target-modules"]),
        )
        set_adapter_state(model, msg.content.array_records["arrays"].to_torch_state_dict())
        device = default_device()
        model.to(device)
        loss, accuracy = test_fn(model, testloader, device=device)
        record_client_metrics(
            partition_id=partition_id, num_examples=sample_count(testloader), loss=loss
        )

    content = RecordDict(
        {
            "metrics": MetricRecord(
                {"num-examples": sample_count(testloader), "loss": loss, "accuracy": accuracy}
            )
        }
    )
    return Message(content=content, reply_to=msg)
