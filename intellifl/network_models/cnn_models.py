"""
Unified CNN architecture for FL experiments.

Replaces 16 per-dataset network definition files with a single parameterizable class.
Architecture configs (channels, hidden sizes, num_classes, input resolution) live in
the dataset registry in __init__.py — no logic here, only structure.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class MedMNISTCNN(nn.Module):
    """
    Parameterizable CNN for all MedMNIST-style FL datasets.

    Supports variable conv depth (2-conv and 3-conv variants) and arbitrary
    input resolutions. Flatten size is computed once at construction via a
    dummy forward pass — no hardcoded spatial arithmetic required.

    Args:
        num_classes:    Number of output classes.
        input_channels: Input channels (1 = grayscale, 3 = RGB).
        input_height:   Image height in pixels (default 28 for MedMNIST).
        input_width:    Image width in pixels (default 28 for MedMNIST).
        conv_channels:  Output channels per conv layer, e.g. [16, 32] or [32, 64, 128].
        fc_hidden:      Hidden FC layer sizes, e.g. [128, 64].
                        A final fc → num_classes is added automatically.
        kernel_size:    Kernel size for all conv layers (default 5, no padding).
        padding:        Padding for all conv layers (default 0 = no padding).
        dropout:        Dropout probabilities, one per fc_hidden layer.
    """

    def __init__(
        self,
        num_classes: int,
        input_channels: int = 1,
        input_height: int = 28,
        input_width: int = 28,
        conv_channels: list[int] | None = None,
        fc_hidden: list[int] | None = None,
        kernel_size: int = 5,
        padding: int = 0,
        dropout: tuple[float, ...] = (0.3, 0.2),
    ) -> None:
        super().__init__()

        if conv_channels is None:
            conv_channels = [16, 32]
        if fc_hidden is None:
            fc_hidden = [128, 64]

        self.pool = nn.MaxPool2d(2, 2)

        # Conv stack — variable depth
        convs: list[nn.Conv2d] = []
        in_ch = input_channels
        for out_ch in conv_channels:
            convs.append(nn.Conv2d(in_ch, out_ch, kernel_size=kernel_size, padding=padding))
            in_ch = out_ch
        self.convs = nn.ModuleList(convs)

        # Named aliases so tests that do `hasattr(net, "conv1")` still pass
        self.conv1 = self.convs[0]
        if len(self.convs) > 1:
            self.conv2 = self.convs[1]

        # Compute flattened size from a dummy pass (handles any input resolution)
        flat = self._compute_flat_size(input_channels, input_height, input_width)

        # FC stack: flat → h1 → h2 → ... → num_classes
        fc_sizes = [flat, *fc_hidden, num_classes]
        self.fcs = nn.ModuleList(
            nn.Linear(fc_sizes[i], fc_sizes[i + 1]) for i in range(len(fc_sizes) - 1)
        )
        self.fc1 = self.fcs[0]  # named alias for test compatibility

        # One dropout layer per hidden FC (pad with 0.0 if fewer rates supplied)
        dropout_rates = list(dropout) + [0.0] * len(fc_hidden)
        self.dropouts = nn.ModuleList(nn.Dropout(dropout_rates[i]) for i in range(len(fc_hidden)))

        self._initialize_weights()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_flat_size(self, channels: int, height: int, width: int) -> int:
        """Run a dummy forward pass to determine the flattened feature size."""
        with torch.no_grad():
            x = torch.zeros(1, channels, height, width)
            for conv in self.convs:
                x = self.pool(F.relu(conv(x)))
            return int(x.view(1, -1).shape[1])

    def _initialize_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_uniform_(m.weight, nonlinearity="relu")
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    # ------------------------------------------------------------------
    # Forward
    # ------------------------------------------------------------------

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for conv in self.convs:
            x = self.pool(F.relu(conv(x)))
        x = torch.flatten(x, 1)
        for i, fc in enumerate(self.fcs[:-1]):
            x = F.relu(fc(x))
            x = self.dropouts[i](x)
        return self.fcs[-1](x)
