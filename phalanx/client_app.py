"""phalanx-fl ClientApp: local LoRA train/eval, adapter-only, OTel-traced.

Each client loads the broadcast adapter weights into a frozen-backbone LoRA model,
trains/evaluates on its non-IID partition, and replies with the updated adapters only.
A client span wraps each local pass so per-partition work shows up in traces.
"""

from __future__ import annotations

import warnings
from typing import Any

import torch
from flwr.app import ArrayRecord, Context, Message, MetricRecord, RecordDict
from flwr.clientapp import ClientApp
from transformers import logging as hf_logging

from phalanx.task import (
    get_adapter_state,
    get_model,
    load_data,
    set_adapter_state,
    set_seed,
    test_fn,
    train_fn,
)
from phalanx.telemetry import client_span, init_telemetry, record_client_metrics

warnings.filterwarnings("ignore", category=FutureWarning)
hf_logging.set_verbosity_error()

app = ClientApp()


def _device() -> torch.device:
    return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def _server_round(msg: Message) -> int:
    config: Any = msg.content.config_records.get("config")
    return int(config["server-round"]) if config and "server-round" in config else 0


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
    set_seed(1000 * rnd + partition_id)  # reproducible per (round, client)

    with client_span(rnd=rnd, partition_id=partition_id, phase="train"):
        trainloader, _ = load_data(
            partition_id,
            num_partitions,
            str(cfg["model-name"]),
            dataset=str(cfg["dataset"]),
            partitioner=str(cfg["partitioner"]),
            alpha=float(cfg["dirichlet-alpha"]),
        )
        model = get_model(str(cfg["model-name"]), num_labels=int(cfg["num-labels"]))
        set_adapter_state(model, msg.content.array_records["arrays"].to_torch_state_dict())
        device = _device()
        model.to(device)
        loss = train_fn(model, trainloader, epochs=int(cfg["local-epochs"]), device=device)
        record_client_metrics(partition_id=partition_id, num_examples=len(trainloader), loss=loss)

    content = RecordDict(
        {
            "arrays": ArrayRecord(get_adapter_state(model)),
            "metrics": MetricRecord({"num-examples": len(trainloader), "train_loss": loss}),
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
    set_seed(1000 * rnd + partition_id)  # reproducible per (round, client)

    with client_span(rnd=rnd, partition_id=partition_id, phase="evaluate"):
        _, testloader = load_data(
            partition_id,
            num_partitions,
            str(cfg["model-name"]),
            dataset=str(cfg["dataset"]),
            partitioner=str(cfg["partitioner"]),
            alpha=float(cfg["dirichlet-alpha"]),
        )
        model = get_model(str(cfg["model-name"]), num_labels=int(cfg["num-labels"]))
        set_adapter_state(model, msg.content.array_records["arrays"].to_torch_state_dict())
        device = _device()
        model.to(device)
        loss, accuracy = test_fn(model, testloader, device=device)
        record_client_metrics(partition_id=partition_id, num_examples=len(testloader), loss=loss)

    content = RecordDict(
        {
            "metrics": MetricRecord(
                {"num-examples": len(testloader), "loss": loss, "accuracy": accuracy}
            )
        }
    )
    return Message(content=content, reply_to=msg)
