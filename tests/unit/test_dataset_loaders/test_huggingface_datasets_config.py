"""Schema tests for `config/huggingface_datasets.json`.

Locks the contract Phase 1A established: every dataset_keyword listed in
`config/dataset_keyword_to_dataset_dir.json` (minus Phase 0A drops) has a
JSON entry with the per-modality fields the future Phase 1B / Phase 2
dispatch will read.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "huggingface_datasets.json"

_REQUIRED_COMMON = {"modality", "hf_dataset_path", "hf_dataset_name", "ref_url"}
_REQUIRED_IMAGE = _REQUIRED_COMMON | {
    "image_column",
    "label_column",
    "num_classes",
    "input_channels",
    "input_height",
    "input_width",
    "image_transformer",
}
_REQUIRED_TEXT = _REQUIRED_COMMON | {"tokenize_columns", "vocabulary_domain"}


@pytest.fixture(scope="module")
def config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def test_total_entry_count(config):
    assert len(config) == 21, "Phase 1A pins the dataset count at 21"


def test_modality_partition(config):
    text = [k for k, v in config.items() if v["modality"] == "text"]
    image = [k for k, v in config.items() if v["modality"] == "image"]
    assert len(text) == 5, f"expected 5 text entries, got {len(text)}: {sorted(text)}"
    assert len(image) == 16, f"expected 16 image entries, got {len(image)}: {sorted(image)}"
    assert set(text) | set(image) == set(config.keys()), "every entry must be image or text"


def test_required_fields_per_modality(config):
    for keyword, entry in config.items():
        missing = (_REQUIRED_IMAGE if entry["modality"] == "image" else _REQUIRED_TEXT) - set(
            entry.keys()
        )
        assert not missing, f"{keyword} missing fields: {sorted(missing)}"


def test_image_entries_have_sane_shape(config):
    for keyword, entry in config.items():
        if entry["modality"] != "image":
            continue
        assert entry["num_classes"] >= 2, f"{keyword}: num_classes must be >= 2"
        assert entry["input_channels"] in (1, 3), (
            f"{keyword}: input_channels must be 1 (grayscale) or 3 (RGB)"
        )
        assert entry["input_height"] > 0 and entry["input_width"] > 0, (
            f"{keyword}: input dims must be positive"
        )


def test_medmnist_grayscale_vs_rgb_matches_n_channels(config):
    """The MedMNIST INFO dict (medmnist/info.py) is the source of truth for
    n_channels per variant; the image_transformer field must agree."""
    medmnist_variants = {
        "pathmnist": 3,
        "dermamnist": 3,
        "octmnist": 1,
        "pneumoniamnist": 1,
        "retinamnist": 3,
        "breastmnist": 1,
        "bloodmnist": 3,
        "tissuemnist": 1,
        "organamnist": 1,
        "organcmnist": 1,
        "organsmnist": 1,
    }
    for variant, channels in medmnist_variants.items():
        entry = config[variant]
        assert entry["input_channels"] == channels, (
            f"{variant}: input_channels={entry['input_channels']} but MedMNIST INFO says {channels}"
        )
        expected_transformer = (
            "medmnist_2d_rgb_image_transformer"
            if channels == 3
            else "medmnist_2d_grayscale_image_transformer"
        )
        assert entry["image_transformer"] == expected_transformer, (
            f"{variant}: image_transformer={entry['image_transformer']!r} "
            f"but channels={channels} requires {expected_transformer!r}"
        )


def test_hf_paths_use_canonical_mirrors(config):
    expected_paths = {
        "pubmed_classification_20k": "ml4pubmed/pubmed-classification-20k",
        "financial_phrasebank": "gtfintechlab/financial_phrasebank_sentences_allagree",
        "lexglue": "coastalcph/lex_glue",
        "medal": "cyrilzakka/pubmed-medline",
        "medquad": "lavita/MedQuAD",
        "cifar100": "uoft-cs/cifar100",
        "cifar10": "uoft-cs/cifar10",
        "cinic10": "flwrlabs/cinic10",
        "femnist_iid": "flwrlabs/femnist",
        "femnist_niid": "flwrlabs/femnist",
    }
    for keyword, expected in expected_paths.items():
        assert config[keyword]["hf_dataset_path"] == expected, (
            f"{keyword}: hf_dataset_path drifted from canonical mirror"
        )

    for variant in (
        "pathmnist",
        "dermamnist",
        "octmnist",
        "pneumoniamnist",
        "retinamnist",
        "breastmnist",
        "bloodmnist",
        "tissuemnist",
        "organamnist",
        "organcmnist",
        "organsmnist",
    ):
        assert config[variant]["hf_dataset_path"] == "albertvillanova/medmnist-v2"
        assert config[variant]["hf_dataset_name"] == variant


def test_dispatch_registry_keywords_have_json_entries(config):
    """Every dataset_keyword in LOADER_REGISTRY must have a JSON entry.

    Reverse direction (every JSON entry has a registry builder) is **not**
    enforced — cifar10 and cinic10 intentionally have JSON entries ahead
    of the Phase 2A transformer wiring.
    """
    from intellifl.dataset_loaders import LOADER_REGISTRY

    for keyword in LOADER_REGISTRY:
        assert keyword in config, f"LOADER_REGISTRY references {keyword!r} but no JSON entry exists"


def test_local_cnn_keywords_have_resolvable_transformer(config):
    """Phase 1B contract: every keyword in `_LOCAL_CNN_KEYWORDS` must point at
    a non-null `image_transformer` field that resolves via
    `resolve_image_transformer` — otherwise `_build_cnn` raises at
    construction time.
    """
    from intellifl.dataset_loaders import _LOCAL_CNN_KEYWORDS, resolve_image_transformer

    for keyword in _LOCAL_CNN_KEYWORDS:
        entry = config[keyword]
        name = entry.get("image_transformer")
        assert name, (
            f"{keyword}: local-CNN dispatch requires a non-null image_transformer "
            f"in huggingface_datasets.json"
        )
        assert resolve_image_transformer(name) is not None


def test_hf_image_cnn_keywords_have_resolvable_transformer(config):
    """Phase 2A contract: every keyword in `_HF_IMAGE_CNN_KEYWORDS` must point
    at a registered `image_transformer` so `_build_hf_image_cnn` resolves
    cleanly. cifar10 / cinic10 / cifar100 cover the current set.
    """
    from intellifl.dataset_loaders import _HF_IMAGE_CNN_KEYWORDS, resolve_image_transformer

    for keyword in _HF_IMAGE_CNN_KEYWORDS:
        entry = config[keyword]
        name = entry.get("image_transformer")
        assert name, f"{keyword}: HF-image-CNN dispatch requires a non-null image_transformer"
        assert resolve_image_transformer(name) is not None
