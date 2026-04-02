"""Visualization and plot data router for simulation results."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from intellifl.api.dependencies import OUTPUT_DIR, get_simulation_path, secure_join
from intellifl.api.models import AllPlotDataResponse, AttackSnapshotsResponse, StrategyPlotData

logger = logging.getLogger(__name__)

router = APIRouter(tags=["visualizations"])

ATTACK_VISUALIZATION_SUFFIXES = {
    "confusion_matrix.png": "confusion_matrix",
    "difference_heatmap.png": "difference_heatmap",
    "samples.html": "html_diff",
    "weight_prediction_grid.png": "prediction_grid",
    "comparison.png": "comparison",
    "weight_histogram.png": "weight_histogram",
    "prediction_comparison.png": "prediction_comparison",
    "weight_layer_delta.png": "weight_layer_delta",
}

KNOWN_ATTACK_VISUALIZATION_SUFFIXES = frozenset(
    {*ATTACK_VISUALIZATION_SUFFIXES.keys(), "visual.png"}
)

VISUALIZATION_FILE_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".html", ".htm"}
)

NON_VISUALIZATION_SUFFIXES = frozenset({"metadata.json", "weight_metadata.json", "summary.json"})


def _to_rel_path(file_path: Path, sim_path: Path) -> str:
    """Normalize a file path to simulation-relative API response format."""
    return str(file_path.relative_to(sim_path)).replace("\\", "/")


def _collect_optional_visualizations(
    round_dir: Path, attack_type: str, sim_path: Path
) -> dict[str, str]:
    """Collect known optional attack visualizations for a given attack type."""
    visualizations: dict[str, str] = {}
    for suffix, key in ATTACK_VISUALIZATION_SUFFIXES.items():
        file_path = round_dir / f"{attack_type}_{suffix}"
        if file_path.is_file():
            visualizations[key] = _to_rel_path(file_path, sim_path)
    return visualizations


def _collect_additional_visualizations(
    round_dir: Path,
    attack_type: str,
    sim_path: Path,
    visualizations: dict[str, Any],
) -> dict[str, str]:
    """Collect unknown visualization artifacts under an additional map."""
    additional: dict[str, str] = {}
    attack_prefix = f"{attack_type}_"

    known_paths = {
        value
        for key, value in visualizations.items()
        if key != "additional" and isinstance(value, str)
    }

    for artifact_path in sorted(round_dir.glob(f"{attack_type}_*")):
        if not artifact_path.is_file():
            continue

        if artifact_path.suffix.lower() not in VISUALIZATION_FILE_EXTENSIONS:
            continue

        artifact_suffix = artifact_path.name[len(attack_prefix) :]
        if (
            artifact_suffix in KNOWN_ATTACK_VISUALIZATION_SUFFIXES
            or artifact_suffix in NON_VISUALIZATION_SUFFIXES
        ):
            continue

        key = Path(artifact_suffix).stem
        if not key:
            continue

        rel_path = _to_rel_path(artifact_path, sim_path)
        if rel_path in known_paths or rel_path in additional.values():
            continue

        additional[key] = rel_path

    return additional


@router.get("/api/simulations/{simulation_id}/plot-data")
async def get_plot_data(simulation_id: str) -> dict:
    """Retrieves JSON plot data for a specific simulation.

    Args:
        simulation_id: The simulation identifier.

    Returns:
        The content of the plot data JSON file.

    Raises:
        HTTPException: If data is unavailable or not found.
    """
    if not all(c.isalnum() or c in "_-" for c in simulation_id):
        raise HTTPException(status_code=400, detail="Invalid simulation ID format.")

    try:
        sim_dir = secure_join(OUTPUT_DIR, simulation_id)

        if not sim_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Simulation directory not found for {simulation_id}",
            )

        json_files = [
            f for f in os.listdir(sim_dir) if f.startswith("plot_data_") and f.endswith(".json")
        ]

        if not json_files:
            raise HTTPException(
                status_code=404,
                detail="Plot data not yet available - simulation may still be running",
            )

        json_path = sim_dir / json_files[0]

        with open(json_path) as f:
            return json.load(f)

    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Plot data not found for simulation {simulation_id}",
        )
    except Exception:
        logger.exception(f"Error loading plot data for {simulation_id}")
        raise HTTPException(status_code=500, detail="Failed to load plot data. Check server logs.")


@router.get("/api/simulations/{simulation_id}/all-plot-data", response_model=AllPlotDataResponse)
async def get_all_plot_data(simulation_id: str) -> AllPlotDataResponse:
    """Retrieves all plot data JSON files for a multi-strategy simulation.

    Args:
        simulation_id: The simulation identifier.

    Returns:
        AllPlotDataResponse containing plot data for each strategy.

    Raises:
        HTTPException: If data is unavailable or not found.
    """
    if not all(c.isalnum() or c in "_-" for c in simulation_id):
        raise HTTPException(status_code=400, detail="Invalid simulation ID format.")

    try:
        sim_dir = secure_join(OUTPUT_DIR, simulation_id)

        if not sim_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Simulation directory not found for {simulation_id}",
            )

        json_files = sorted(
            [f for f in os.listdir(sim_dir) if f.startswith("plot_data_") and f.endswith(".json")]
        )

        if not json_files:
            raise HTTPException(
                status_code=404,
                detail="Plot data not yet available - simulation may still be running",
            )

        all_plot_data = []
        for json_file in json_files:
            json_path = sim_dir / json_file
            with open(json_path) as f:
                data = json.load(f)
                strategy_num = int(json_file.replace("plot_data_", "").replace(".json", ""))
                all_plot_data.append(StrategyPlotData(strategy_number=strategy_num, data=data))

        return AllPlotDataResponse(strategies=all_plot_data)

    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Plot data not found for simulation {simulation_id}",
        )
    except Exception:
        logger.exception(f"Error loading all plot data for {simulation_id}")
        raise HTTPException(status_code=500, detail="Failed to load plot data. Check server logs.")


@router.get(
    "/api/simulations/{simulation_id}/attack-snapshots", response_model=AttackSnapshotsResponse
)
async def get_attack_snapshots(
    simulation_id: str, sim_path: Path = Depends(get_simulation_path)
) -> dict[str, Any]:
    """Retrieves attack snapshot data for visualization.

    Args:
        simulation_id: The simulation identifier.
        sim_path: The validated path to the simulation directory.

    Returns:
        A dictionary containing snapshot summaries, timelines, and image paths
        including additional visualizations (confusion matrices, heatmaps, etc.).
    """
    snapshot_dirs = sorted(sim_path.glob("attack_snapshots_*"))

    if not snapshot_dirs:
        return {"has_snapshots": False, "strategies": []}

    strategies_data = []

    for snapshot_dir in snapshot_dirs:
        strategy_num = int(snapshot_dir.name.replace("attack_snapshots_", ""))

        summary_path = snapshot_dir / "summary.json"
        summary = None
        if summary_path.is_file():
            try:
                with summary_path.open("r") as f:
                    summary = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to load attack summary: {summary_path}: {e}")

        snapshots = []
        for client_dir in sorted(snapshot_dir.glob("client_*")):
            client_id = int(client_dir.name.replace("client_", ""))

            for round_dir in sorted(client_dir.glob("round_*")):
                round_num = int(round_dir.name.replace("round_", ""))

                visual_files = list(round_dir.glob("*_visual.png"))
                for visual_file in visual_files:
                    attack_type = visual_file.stem.replace("_visual", "")
                    primary_path = _to_rel_path(visual_file, sim_path)

                    metadata = None
                    metadata_path = round_dir / f"{attack_type}_metadata.json"
                    if metadata_path.is_file():
                        try:
                            with metadata_path.open("r") as f:
                                metadata = json.load(f)
                        except (OSError, json.JSONDecodeError) as e:
                            logger.warning(f"Failed to load attack metadata: {metadata_path}: {e}")

                    visualizations: dict[str, Any] = {"primary": primary_path}
                    visualizations.update(
                        _collect_optional_visualizations(round_dir, attack_type, sim_path)
                    )
                    additional_viz = _collect_additional_visualizations(
                        round_dir, attack_type, sim_path, visualizations
                    )
                    if additional_viz:
                        visualizations["additional"] = additional_viz

                    snapshot_data = {
                        "client_id": client_id,
                        "round_num": round_num,
                        "attack_type": attack_type,
                        "image_path": primary_path,
                        "visualizations": visualizations,
                        "metadata": metadata,
                    }

                    flip_summary = None
                    flip_summary_path = round_dir / f"{attack_type}_summary.json"
                    if flip_summary_path.is_file():
                        try:
                            with flip_summary_path.open("r") as f:
                                flip_summary = json.load(f)
                        except (OSError, json.JSONDecodeError) as e:
                            logger.warning(f"Failed to load flip summary: {flip_summary_path}: {e}")

                    if flip_summary:
                        snapshot_data["flip_summary"] = flip_summary

                    snapshots.append(snapshot_data)

                html_files = list(round_dir.glob("*_samples.html"))
                for html_file in html_files:
                    attack_type = html_file.stem.replace("_samples", "")
                    if not any(
                        s["attack_type"] == attack_type
                        and s["client_id"] == client_id
                        and s["round_num"] == round_num
                        for s in snapshots
                    ):
                        html_visualizations: dict[str, Any] = {
                            "html_diff": _to_rel_path(html_file, sim_path),
                        }
                        html_visualizations.update(
                            _collect_optional_visualizations(round_dir, attack_type, sim_path)
                        )
                        additional_viz = _collect_additional_visualizations(
                            round_dir, attack_type, sim_path, html_visualizations
                        )
                        if additional_viz:
                            html_visualizations["additional"] = additional_viz

                        metadata = None
                        metadata_path = round_dir / f"{attack_type}_metadata.json"
                        if metadata_path.is_file():
                            try:
                                with metadata_path.open("r") as f:
                                    metadata = json.load(f)
                            except (OSError, json.JSONDecodeError) as e:
                                logger.warning(
                                    f"Failed to load attack metadata: {metadata_path}: {e}"
                                )

                        snapshots.append(
                            {
                                "client_id": client_id,
                                "round_num": round_num,
                                "attack_type": attack_type,
                                "image_path": "",
                                "visualizations": html_visualizations,
                                "metadata": metadata,
                                "is_text_attack": True,
                            }
                        )

                histogram_files = list(round_dir.glob("*_weight_histogram.png"))
                for hist_file in histogram_files:
                    attack_type = hist_file.stem.replace("_weight_histogram", "")

                    existing = next(
                        (
                            s
                            for s in snapshots
                            if s["client_id"] == client_id
                            and s["round_num"] == round_num
                            and s["attack_type"] == attack_type
                        ),
                        None,
                    )

                    hist_rel_path = _to_rel_path(hist_file, sim_path)

                    if existing:
                        if "visualizations" not in existing:
                            existing["visualizations"] = {}  # type: ignore[index]
                        existing["visualizations"]["weight_histogram"] = hist_rel_path  # type: ignore[index]
                    else:
                        hist_visualizations: dict[str, Any] = {"weight_histogram": hist_rel_path}
                        hist_visualizations.update(
                            _collect_optional_visualizations(round_dir, attack_type, sim_path)
                        )

                        if "prediction_comparison" in hist_visualizations:
                            hist_visualizations["primary"] = hist_visualizations[
                                "prediction_comparison"
                            ]
                        elif "prediction_grid" in hist_visualizations:
                            hist_visualizations["primary"] = hist_visualizations["prediction_grid"]
                        else:
                            hist_visualizations["primary"] = hist_rel_path

                        additional_viz = _collect_additional_visualizations(
                            round_dir, attack_type, sim_path, hist_visualizations
                        )
                        if additional_viz:
                            hist_visualizations["additional"] = additional_viz

                        weight_metadata = None
                        weight_meta_path = round_dir / f"{attack_type}_weight_metadata.json"
                        if weight_meta_path.is_file():
                            try:
                                with weight_meta_path.open("r") as f:
                                    weight_metadata = json.load(f)
                            except (OSError, json.JSONDecodeError) as e:
                                logger.warning(
                                    f"Failed to load weight metadata: {weight_meta_path}: {e}"
                                )

                        snapshots.append(
                            {
                                "client_id": client_id,
                                "round_num": round_num,
                                "attack_type": attack_type,
                                "image_path": hist_visualizations.get("primary", ""),
                                "visualizations": hist_visualizations,
                                "metadata": weight_metadata,
                                "is_weight_attack": True,
                            }
                        )

        strategies_data.append(
            {
                "strategy_number": strategy_num,
                "summary": summary,
                "snapshots": sorted(snapshots, key=lambda x: (x["round_num"], x["client_id"])),
            }
        )

    return {
        "has_snapshots": True,
        "strategies": strategies_data,
    }
