from __future__ import annotations

from torchvision import transforms

# research(2026-05): canonical CIFAR-10 RGB statistics, used widely in
# PyTorch benchmarks since Krizhevsky 2009. Verified via 2026-05 web-search
# against kuangliu/pytorch-cifar + AntonFriberg/pytorch-cinic-10 reference
# implementations and the PyTorch community discuss thread on CIFAR-10
# normalization. The CIFAR-100 sibling uses different stats; both kept
# separate rather than collapsing because the per-channel divergence is
# real (CIFAR-10 mean R=0.4914 vs CIFAR-100 mean R=0.5071).
cifar10_image_transformer = transforms.Compose(
    [
        transforms.Resize((32, 32)),
        transforms.ToTensor(),
        transforms.Normalize(mean=(0.4914, 0.4822, 0.4465), std=(0.2470, 0.2435, 0.2616)),
    ]
)
