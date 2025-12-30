from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class LungCancerCNN(nn.Module):
    def __init__(self, num_classes=4):
        super().__init__()

        self.conv1 = nn.Conv2d(1, 16, kernel_size=3, padding=1)  # Grayscale image (1 channel)
        self.pool = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.conv3 = nn.Conv2d(32, 64, kernel_size=3, padding=1)

        # Dynamically compute flattened feature size
        self._to_linear: int = self._compute_flatten_size()

        self.fc1 = nn.Linear(self._to_linear, 128)
        self.dropout1 = nn.Dropout(0.3)
        self.fc2 = nn.Linear(128, 64)
        self.dropout2 = nn.Dropout(0.2)
        self.fc3 = nn.Linear(64, num_classes)

        self._initialize_weights()

    def _compute_flatten_size(self) -> int:
        with torch.no_grad():
            x = torch.zeros(1, 1, 224, 224)  # Input size of your images
            x = self.pool(F.relu(self.conv1(x)))
            x = self.pool(F.relu(self.conv2(x)))
            x = self.pool(F.relu(self.conv3(x)))
            return int(x.view(1, -1).shape[1])

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = self.pool(F.relu(self.conv3(x)))
        x = x.view(x.size(0), -1)  # Flatten
        x = F.relu(self.fc1(x))
        x = self.dropout1(x)
        x = F.relu(self.fc2(x))
        x = self.dropout2(x)
        x = self.fc3(x)
        return x

    def _initialize_weights(self):
        """Random weight initialization"""

        nn.init.kaiming_uniform_(self.conv1.weight, nonlinearity="relu")
        nn.init.kaiming_uniform_(self.conv2.weight, nonlinearity="relu")
        nn.init.kaiming_uniform_(self.conv3.weight, nonlinearity="relu")

        nn.init.xavier_uniform_(self.fc1.weight)
        nn.init.xavier_uniform_(self.fc2.weight)
        nn.init.xavier_uniform_(self.fc3.weight)

        if self.conv1.bias is not None:
            nn.init.zeros_(self.conv1.bias)
        if self.conv2.bias is not None:
            nn.init.zeros_(self.conv2.bias)
        if self.conv3.bias is not None:
            nn.init.zeros_(self.conv3.bias)
        if self.fc1.bias is not None:
            nn.init.zeros_(self.fc1.bias)
        if self.fc2.bias is not None:
            nn.init.zeros_(self.fc2.bias)
        if self.fc3.bias is not None:
            nn.init.zeros_(self.fc3.bias)
