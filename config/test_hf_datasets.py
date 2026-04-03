"""
Unified smoke-test script for ALL HuggingFace datasets in huggingface_datasets.json.

Reads the config, detects modality (text / image / 3d_image / …), and runs a
quick end-to-end load for each entry to verify the pipeline works.

Usage:
    python config/test_hf_datasets.py                # test all datasets
    python config/test_hf_datasets.py cifar100        # test one by keyword
    python config/test_hf_datasets.py --modality image  # test all image datasets
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

# ------------------------------------------------------------------
# Resolve paths so the script works when invoked from the repo root
# ------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

CONFIG_PATH = REPO_ROOT / "config" / "huggingface_datasets.json"

# ------------------------------------------------------------------
# Image transformer registry (mirrors federated_simulation.py)
# ------------------------------------------------------------------
_IMAGE_TRANSFORMERS: dict[str, object] = {}


def _get_image_transformer(name: str | None):
    """Lazily import and cache image transformers by config key."""
    if name is None:
        return None
    if not _IMAGE_TRANSFORMERS:
        from intellifl.dataset_loaders.image_transformers.cifar100_image_transformer import (
            cifar100_image_transformer,
        )
        from intellifl.dataset_loaders.image_transformers.femnist_image_transformer import (
            femnist_image_transformer,
        )
        from intellifl.dataset_loaders.image_transformers.flair_image_transformer import (
            flair_image_transformer,
        )
        from intellifl.dataset_loaders.image_transformers.its_image_transformer import (
            its_image_transformer,
        )
        from intellifl.dataset_loaders.image_transformers.lung_photos_image_transformer import (
            lung_cancer_image_transformer,
        )
        from intellifl.dataset_loaders.image_transformers.medmnist_2d_grayscale_image_transformer import (
            medmnist_2d_grayscale_image_transformer,
        )
        from intellifl.dataset_loaders.image_transformers.medmnist_2d_rgb_image_transformer import (
            medmnist_2d_rgb_image_transformer,
        )

        _IMAGE_TRANSFORMERS.update(
            {
                "cifar100_image_transformer": cifar100_image_transformer,
                "medmnist_2d_rgb_image_transformer": medmnist_2d_rgb_image_transformer,
                "medmnist_2d_grayscale_image_transformer": medmnist_2d_grayscale_image_transformer,
                "femnist_image_transformer": femnist_image_transformer,
                "flair_image_transformer": flair_image_transformer,
                "its_image_transformer": its_image_transformer,
                "lung_cancer_image_transformer": lung_cancer_image_transformer,
            }
        )
    if name not in _IMAGE_TRANSFORMERS:
        raise ValueError(
            f"Unknown image_transformer '{name}'. Available: {sorted(_IMAGE_TRANSFORMERS)}"
        )
    return _IMAGE_TRANSFORMERS[name]


# ------------------------------------------------------------------
# Per-modality test runners
# ------------------------------------------------------------------


def _test_text_dataset(keyword: str, cfg: dict, max_samples: int = 100) -> None:
    """Smoke-test a HuggingFace **text** dataset entry."""
    from intellifl.dataset_loaders.huggingface_text_dataset_loader import (
        HuggingFaceTextDatasetLoader,
    )

    loader = HuggingFaceTextDatasetLoader(
        hf_dataset_path=cfg["hf_dataset_path"],
        hf_dataset_name=cfg.get("hf_dataset_name"),
        tokenize_columns=cfg.get("tokenize_columns", ["text"]),
        remove_columns=cfg.get("remove_columns"),
        num_of_clients=2,
        batch_size=8,
        max_samples=max_samples,
    )
    trainloaders, valloaders = loader.load_datasets()

    assert len(trainloaders) == 2, f"Expected 2 trainloaders, got {len(trainloaders)}"
    assert len(valloaders) == 2, f"Expected 2 valloaders, got {len(valloaders)}"
    print(f"  loaders: {len(trainloaders)} train, {len(valloaders)} val")


def _test_image_dataset(keyword: str, cfg: dict, max_samples: int = 100) -> None:
    """Smoke-test a HuggingFace **image** dataset entry."""
    from intellifl.dataset_loaders.huggingface_image_dataset_loader import (
        HuggingFaceImageDatasetLoader,
    )

    transformer = _get_image_transformer(cfg.get("image_transformer"))

    loader = HuggingFaceImageDatasetLoader(
        hf_dataset_path=cfg["hf_dataset_path"],
        hf_dataset_name=cfg.get("hf_dataset_name"),
        transformer=transformer,
        num_of_clients=2,
        batch_size=8,
        max_samples=max_samples,
        image_column=cfg.get("image_column", "image"),
        label_column=cfg.get("label_column", "label"),
    )
    trainloaders, valloaders = loader.load_datasets()

    assert len(trainloaders) == 2, f"Expected 2 trainloaders, got {len(trainloaders)}"
    assert len(valloaders) == 2, f"Expected 2 valloaders, got {len(valloaders)}"
    print(f"  loaders: {len(trainloaders)} train, {len(valloaders)} val")

    # Verify a batch has the right shape if dimensions are declared
    if cfg.get("input_channels") and cfg.get("input_height") and cfg.get("input_width"):
        batch = next(iter(trainloaders[0]))
        images, labels = batch
        c, h, w = cfg["input_channels"], cfg["input_height"], cfg["input_width"]
        assert images.shape[1:] == (c, h, w), (
            f"Expected image shape (*, {c}, {h}, {w}), got {tuple(images.shape)}"
        )
        print(f"  batch shape: {tuple(images.shape)}, labels shape: {tuple(labels.shape)}")


def _test_3d_image_dataset(keyword: str, cfg: dict, max_samples: int = 100) -> None:
    """Smoke-test a HuggingFace **3D image** dataset entry (placeholder)."""
    # 3D image datasets are not yet wired into a loader, so just validate
    # that the config is well-formed and the dataset is reachable.
    from datasets import load_dataset  # type: ignore[attr-defined]

    ds = load_dataset(
        cfg["hf_dataset_path"],
        cfg.get("hf_dataset_name"),
        split="train",
        streaming=True,
        trust_remote_code=True,
    )
    sample = next(iter(ds))
    print(f"  streaming sample keys: {list(sample.keys())}")
    print("  (3D image loader not yet implemented — config validation only)")


# Dispatcher: modality string → test function
_MODALITY_RUNNERS = {
    "text": _test_text_dataset,
    "image": _test_image_dataset,
    "3d_image": _test_3d_image_dataset,
}


# ------------------------------------------------------------------
# Orchestration
# ------------------------------------------------------------------


def load_config() -> dict:
    """Load and return the full huggingface_datasets.json config."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_dataset(keyword: str, cfg: dict, max_samples: int = 100) -> bool:
    """Run the appropriate smoke test for a single dataset entry.

    Returns True on success, False on failure.
    """
    modality = cfg.get("modality", "unknown")
    runner = _MODALITY_RUNNERS.get(modality)

    print(f"\n{'=' * 60}")
    print(f"[{keyword}]  modality={modality}  path={cfg.get('hf_dataset_path')}")
    print(f"{'=' * 60}")

    if runner is None:
        print(f"  WARNING: No test runner for modality '{modality}'. Skipping.")
        return True  # not a failure — just unsupported

    try:
        runner(keyword, cfg, max_samples=max_samples)
        print("  PASSED")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test HuggingFace datasets from config.")
    parser.add_argument(
        "keywords",
        nargs="*",
        help="Dataset keyword(s) to test. If omitted, tests all.",
    )
    parser.add_argument(
        "--modality",
        choices=list(_MODALITY_RUNNERS.keys()),
        help="Only test datasets of this modality.",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=100,
        help="Max samples per dataset for quick testing (default: 100).",
    )
    args = parser.parse_args()

    all_configs = load_config()

    # Filter to requested keywords and/or modality
    targets: dict[str, dict] = {}
    for kw, cfg in all_configs.items():
        if args.keywords and kw not in args.keywords:
            continue
        if args.modality and cfg.get("modality") != args.modality:
            continue
        targets[kw] = cfg

    if not targets:
        print("No matching datasets found in config.")
        sys.exit(1)

    print(f"Testing {len(targets)} dataset(s): {', '.join(targets.keys())}")
    print(f"Max samples per dataset: {args.max_samples}")

    results: dict[str, bool] = {}
    for kw, cfg in targets.items():
        results[kw] = test_dataset(kw, cfg, max_samples=args.max_samples)

    # Summary
    passed = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)
    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {passed} passed, {failed} failed out of {len(results)} tested")
    print(f"{'=' * 60}")

    if failed:
        print("\nFailed datasets:")
        for kw, ok in results.items():
            if not ok:
                print(f"  - {kw}")
        sys.exit(1)


if __name__ == "__main__":
    main()
