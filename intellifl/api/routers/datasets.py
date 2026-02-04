"""Dataset validation router for HuggingFace datasets."""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter

from datasets import load_dataset_builder  # type: ignore[attr-defined]
from intellifl.api.models import DatasetInfo, DatasetValidationResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["datasets"])


@router.get("/api/datasets/validate", response_model=DatasetValidationResponse)
async def validate_dataset(name: str) -> DatasetValidationResponse:
    """Validates if a HuggingFace dataset exists and is compatible with Flower.

    Args:
        name: The HuggingFace dataset identifier.

    Returns:
        DatasetValidationResponse indicating validity, compatibility, and metadata.
    """
    try:
        builder = load_dataset_builder(name)

        if builder.info.splits is None:
            return DatasetValidationResponse(
                valid=False,
                compatible=False,
                reason="Dataset has no splits information",
            )

        splits = list(builder.info.splits.keys())
        num_examples = sum(s.num_examples for s in builder.info.splits.values())
        features = str(builder.info.features)

        label_field_indicators = [
            "label",
            "labels",
            "class",
            "target",
            "fine_label",
            "coarse_label",
        ]
        has_label = any(field in features.lower() for field in label_field_indicators)

        key_features = []
        if builder.info.features:
            try:
                feature_matches = re.findall(r"(?:['\"](\w+)['\"]|(\w+))\s*:", features)
                feature_matches = [m[0] or m[1] for m in feature_matches]
                if feature_matches:
                    key_features = list(dict.fromkeys(feature_matches))[:5]
            except Exception as e:
                logger.debug(f"Failed to parse dataset features: {e}")
                key_features = []

        compatible = True

        return DatasetValidationResponse(
            valid=True,
            compatible=compatible,
            info=DatasetInfo(
                splits=splits,
                num_examples=num_examples,
                features=features,
                has_label=has_label,
                key_features=key_features,
            ),
            error=None,
        )

    except Exception as e:
        error_message = str(e)
        error_lower = error_message.lower()

        if "connection" in error_lower or "network" in error_lower or "timeout" in error_lower:
            error_message = "Network error: Unable to connect to HuggingFace Hub. Please check your internet connection."
        elif "not found" in error_lower or "doesn't exist" in error_lower or "404" in error_lower:
            error_message = (
                f"Dataset '{name}' not found on HuggingFace Hub. Please verify the dataset name."
            )
        elif (
            "authentication" in error_lower or "unauthorized" in error_lower or "401" in error_lower
        ):
            error_message = "Authentication error: This dataset may require HuggingFace login or access permissions."
        elif "forbidden" in error_lower or "403" in error_lower:
            error_message = "Access forbidden: You may not have permission to access this dataset."
        elif len(name) < 2 or "/" not in name:
            error_message = "Invalid dataset name format. Expected format: 'username/dataset-name' (e.g., 'ylecun/mnist')."
        else:
            error_message = f"Unable to validate dataset: {error_message}"

        return DatasetValidationResponse(
            valid=False,
            compatible=False,
            info=None,
            error=error_message,
        )
