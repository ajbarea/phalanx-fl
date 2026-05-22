from __future__ import annotations

from torchvision import transforms

# research(2026-05): CINIC-10 RGB statistics from BayesWatch/cinic-10
# (Darlow et al. 2018, arXiv:1810.03505). Reference impl
# AntonFriberg/pytorch-cinic-10 uses these exact values. CINIC-10 mixes
# CIFAR-10 + downsampled ImageNet patches, so the mean+std diverge from
# plain CIFAR-10 (notably blue channel mean 0.430 vs CIFAR-10's 0.447).
cinic10_image_transformer = transforms.Compose(
    [
        transforms.Resize((32, 32)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=(0.47889522, 0.47227842, 0.43047404),
            std=(0.24205776, 0.23828046, 0.25874835),
        ),
    ]
)
