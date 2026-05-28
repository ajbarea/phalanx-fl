"""
HTML and JSON reporting utilities for attack snapshots.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from intellifl.simulation_strategies.termination_policies import read_termination_summary

from .attack_snapshots import (
    get_snapshot_summary,
    list_attack_snapshots,
    load_attack_snapshot,
)
from .snapshot_animation import save_attack_timeline_gif
from .weight_poisoning import is_weight_attack


def _get_snapshots_dir_checked(output_dir: str, strategy_number: int = 0) -> Path | None:
    """Get snapshots directory path, returning None if it doesn't exist."""
    snapshots_dir = Path(output_dir) / f"attack_snapshots_{strategy_number}"
    if not snapshots_dir.exists():
        logging.warning(f"No attack_snapshots_{strategy_number} directory found in {output_dir}")
        return None
    return snapshots_dir


def _extract_attack_params_for_display(attack_type: str, attack_config: dict) -> list:
    """Extract attack parameters formatted as strings for HTML display."""
    html_attack_params = []
    if attack_type == "label_flipping":
        pass
    elif attack_type == "gaussian_noise":
        html_attack_params.append(f"SNR={attack_config.get('target_noise_snr', '?')}dB")
        html_attack_params.append(f"ratio={attack_config.get('attack_ratio', '?')}")
    elif attack_type == "token_replacement":
        vocab = attack_config.get("target_vocabulary")
        strategy = attack_config.get("replacement_strategy")
        prob = attack_config.get("replacement_prob", attack_config.get("replacement_probability"))
        if vocab:
            html_attack_params.append(f"vocab={vocab}")
        if strategy:
            html_attack_params.append(f"strategy={strategy}")
        if prob is not None:
            html_attack_params.append(f"prob={prob}")
    elif attack_type == "targeted_label_flipping":
        html_attack_params.append(f"src={attack_config.get('source_class', '?')}")
        html_attack_params.append(f"tgt={attack_config.get('target_class', '?')}")
        html_attack_params.append(f"ratio={attack_config.get('flip_ratio', '1.0')}")
    elif attack_type == "backdoor_trigger":
        html_attack_params.append(f"target={attack_config.get('target_class', '?')}")
        html_attack_params.append(f"pattern={attack_config.get('trigger_pattern', 'square')}")
        html_attack_params.append(f"ratio={attack_config.get('poison_ratio', '?')}")
    elif attack_type == "boosted_scaling":
        html_attack_params.append(f"n_total={attack_config.get('n_total', '?')}")
        html_attack_params.append(f"n_mal={attack_config.get('n_malicious', '1')}")
        html_attack_params.append(f"boost={attack_config.get('boost_factor', '1.0')}")
    elif attack_type == "model_poisoning":
        html_attack_params.append(f"ratio={attack_config.get('poison_ratio', '0.1')}")
        html_attack_params.append(f"mag={attack_config.get('magnitude', '5.0')}")
    elif attack_type == "gradient_scaling":
        html_attack_params.append(f"scale={attack_config.get('scale_factor', '2.0')}")
    elif attack_type == "byzantine_perturbation":
        html_attack_params.append(f"noise={attack_config.get('noise_scale', '3.0')}")
        clip_norm = attack_config.get("clip_norm")
        if clip_norm is not None:
            html_attack_params.append(f"clip={clip_norm}")
    elif attack_type == "inner_product_manipulation":
        html_attack_params.append(f"strength={attack_config.get('perturbation_strength', '?')}")
        html_attack_params.append(f"dir={attack_config.get('target_direction', 'negative')}")
    elif attack_type == "alternating_min_poisoning":
        html_attack_params.append(f"n_total={attack_config.get('n_total', '?')}")
        html_attack_params.append(f"n_mal={attack_config.get('n_malicious', '1')}")
        html_attack_params.append(f"tau={attack_config.get('tau_factor', '1.0')}")
        html_attack_params.append(f"steps={attack_config.get('pgd_steps', '20')}")
        html_attack_params.append(f"step_size={attack_config.get('pgd_step_size', '?')}")
    return html_attack_params


def _split_composite_attack_info(attack_type: str, attack_configs: list) -> list:
    """Split composite attack into individual entries with type and params."""
    attack_info = []
    for config in attack_configs:
        config_type = config.get("attack_type", "unknown")
        params = _extract_attack_params_for_display(config_type, config)
        attack_info.append({"type": config_type, "params": params})

    return attack_info


def _resolve_primary_and_extra_visuals(
    snapshots_dir: Path,
    client_id: int,
    round_num: int,
    attack_type: str,
    preferred_visual: Path | None,
) -> tuple[str | None, list[str]]:
    """Resolve primary visual path and additional visual artifacts for an attack row."""
    round_dir = snapshots_dir / f"client_{client_id}" / f"round_{round_num}"
    png_paths = sorted(round_dir.glob(f"{attack_type}*.png"))
    rel_png_paths = [p.relative_to(snapshots_dir).as_posix() for p in png_paths]

    primary_visual_path: str | None = None
    if preferred_visual is not None and (snapshots_dir / preferred_visual).exists():
        primary_visual_path = preferred_visual.as_posix()
    elif rel_png_paths:
        primary_visual_path = rel_png_paths[0]

    extra_visual_paths = [p for p in rel_png_paths if p != primary_visual_path]
    return primary_visual_path, extra_visual_paths


def generate_summary_json(
    output_dir: str, run_config: dict | None = None, strategy_number: int = 0
) -> None:
    """Generate summary.json for attack snapshots.

    Args:
        output_dir: Base output directory
        run_config: Run configuration dict (optional)
        strategy_number: Strategy index (default: 0)

    Note:
        Creates summary.json file in the snapshots directory with metadata
        about all snapshots, grouped by round and client.
    """
    snapshots_dir = _get_snapshots_dir_checked(output_dir, strategy_number)
    if not snapshots_dir:
        return

    summary = get_snapshot_summary(output_dir, strategy_number)

    run_id = Path(output_dir).name
    full_summary = {
        "experiment": {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
        },
        "attack_summary": summary,
        "attack_timeline": {},
    }

    if run_config:
        full_summary["experiment"]["total_clients"] = run_config.get("num_of_clients", "Unknown")
        full_summary["experiment"]["total_rounds"] = run_config.get("num_of_rounds", "Unknown")
        full_summary["experiment"]["config_file"] = f"strategy_config_{strategy_number}.json"

    snapshots = list_attack_snapshots(output_dir, strategy_number)
    for snapshot_path in snapshots:
        snapshot = load_attack_snapshot(str(snapshot_path))
        if snapshot:
            metadata = snapshot.get("metadata", snapshot)
            client_id = str(metadata.get("client_id"))
            round_num = str(metadata.get("round_num"))
            attack_type = metadata.get("attack_type")

            if client_id not in full_summary["attack_timeline"]:
                full_summary["attack_timeline"][client_id] = {}

            if round_num not in full_summary["attack_timeline"][client_id]:
                full_summary["attack_timeline"][client_id][round_num] = []

            full_summary["attack_timeline"][client_id][round_num].append(attack_type)

    summary_path = snapshots_dir / "summary.json"
    try:
        with open(summary_path, "w") as f:
            json.dump(full_summary, f, indent=2)
        logging.debug(f"Generated attack summary: {summary_path}")
    except Exception as e:
        logging.warning(f"Failed to generate summary.json: {e}")

    # Generate attack timeline animation if there are attacks
    if full_summary["attack_timeline"]:
        try:
            total_rounds = int(full_summary["experiment"].get("total_rounds", 10))
            total_clients = int(full_summary["experiment"].get("total_clients", 5))
            attack_types = full_summary["attack_summary"].get("attack_types", [])

            timeline_gif_path = snapshots_dir / "attack_timeline.gif"
            save_attack_timeline_gif(
                attack_timeline=full_summary["attack_timeline"],
                filepath=timeline_gif_path,
                total_rounds=total_rounds,
                total_clients=total_clients,
                attack_types=attack_types,
            )
        except Exception as e:
            logging.warning(f"Failed to generate attack timeline animation: {e}")


def generate_snapshot_index(
    output_dir: str, run_config: dict | None = None, strategy_number: int = 0
) -> None:
    """Generate snapshot index HTML report.

    Creates an interactive HTML report showing all attack snapshots with
    filtering, navigation, and visual previews.

    Args:
        output_dir: Base output directory
        run_config: Run configuration dict (optional)
        strategy_number: Strategy index (default: 0)

    Note:
        Generates both summary.json and index.html files in snapshots directory.
    """
    snapshots_dir = _get_snapshots_dir_checked(output_dir, strategy_number)
    if not snapshots_dir:
        return

    snapshots = list_attack_snapshots(output_dir, strategy_number)
    snapshot_data = []

    for snapshot_path in snapshots:
        snapshot = load_attack_snapshot(str(snapshot_path))
        if snapshot:
            metadata = snapshot.get("metadata", snapshot)
            attack_config = metadata.get("attack_config", {})
            attack_type = metadata.get("attack_type", "unknown")
            client_id = metadata.get("client_id")
            round_num = metadata.get("round_num")

            if isinstance(attack_config, list) and len(attack_config) > 1:
                attack_info_list = _split_composite_attack_info(attack_type, attack_config)

                attack_types = [info["type"] for info in attack_info_list]
                all_params = []
                for info in attack_info_list:
                    if info["params"]:
                        all_params.extend(info["params"])

                synopsis_rel_path = (
                    Path(f"client_{client_id}") / f"round_{round_num}" / "composite_synopsis.png"
                )
                stacked_visual_path = (
                    synopsis_rel_path
                    if (snapshots_dir / synopsis_rel_path).exists()
                    else (
                        Path(f"client_{client_id}")
                        / f"round_{round_num}"
                        / f"{attack_type}_visual.png"
                    )
                )

                snapshot_data.append(
                    {
                        "client": client_id,
                        "round": round_num,
                        "attack_types": attack_types,
                        "is_stacked": True,
                        "samples": metadata.get("num_samples", 0),
                        "parameters": ", ".join(all_params) if all_params else "N/A",
                        "pickle_path": snapshot_path.relative_to(snapshots_dir).as_posix(),
                        "pickle_title": "Download snapshot data",
                        "visual_path": stacked_visual_path.as_posix(),
                        "visual_type": "image",
                        "additional_visuals": [],
                        "metadata_path": (
                            Path(f"client_{client_id}")
                            / f"round_{round_num}"
                            / f"{attack_type}_metadata.json"
                        ).as_posix(),
                    }
                )
            else:
                if isinstance(attack_config, list):
                    attack_config = attack_config[0] if attack_config else {}

                attack_parameters = _extract_attack_params_for_display(attack_type, attack_config)

                if is_weight_attack(attack_type):
                    preferred_visual = (
                        Path(f"client_{client_id}")
                        / f"round_{round_num}"
                        / (f"{attack_type}_weight_histogram.png")
                    )
                    visual_type = "image"
                    metadata_filename = f"{attack_type}_weight_metadata.json"
                    download_title = "Download weight snapshot metadata"
                elif attack_type == "token_replacement":
                    preferred_visual = (
                        Path(f"client_{client_id}")
                        / f"round_{round_num}"
                        / (f"{attack_type}_samples.txt")
                    )
                    visual_type = "text"
                    metadata_filename = f"{attack_type}_metadata.json"
                    download_title = "Download pickle file"
                else:
                    preferred_visual = (
                        Path(f"client_{client_id}")
                        / f"round_{round_num}"
                        / (f"{attack_type}_visual.png")
                    )
                    visual_type = "image"
                    metadata_filename = f"{attack_type}_metadata.json"
                    download_title = "Download pickle file"

                if visual_type == "image":
                    visual_path, extra_visuals = _resolve_primary_and_extra_visuals(
                        snapshots_dir=snapshots_dir,
                        client_id=client_id,
                        round_num=round_num,
                        attack_type=attack_type,
                        preferred_visual=preferred_visual,
                    )
                else:
                    visual_path = (
                        preferred_visual.as_posix()
                        if (snapshots_dir / preferred_visual).exists()
                        else None
                    )
                    extra_visuals = []

                sample_count = metadata.get("num_samples")
                if sample_count is None and is_weight_attack(attack_type):
                    sample_count = (
                        metadata.get("statistics", {}).get("before", {}).get("num_layers", 0)
                    )

                snapshot_data.append(
                    {
                        "client": client_id,
                        "round": round_num,
                        "attack_types": [attack_type],
                        "is_stacked": False,
                        "samples": sample_count if sample_count is not None else 0,
                        "parameters": (
                            ", ".join(attack_parameters) if attack_parameters else "N/A"
                        ),
                        "pickle_path": snapshot_path.relative_to(snapshots_dir).as_posix(),
                        "pickle_title": download_title,
                        "visual_path": visual_path,
                        "visual_type": visual_type,
                        "additional_visuals": [
                            {
                                "path": rel_path,
                                "title": f"View {Path(rel_path).name}",
                                "icon": "📊",
                            }
                            for rel_path in extra_visuals
                        ],
                        "metadata_path": (
                            Path(f"client_{client_id}") / f"round_{round_num}" / metadata_filename
                        ).as_posix(),
                    }
                )

    snapshot_data.sort(key=lambda x: (x["client"], x["round"]))

    html_content = _generate_index_html(
        snapshot_data,
        output_dir,
        run_config,
        (snapshots_dir / "attack_timeline.gif").exists(),
    )

    index_path = snapshots_dir / "index.html"
    try:
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logging.debug(f"Generated attack snapshot index: {index_path}")
    except Exception as e:
        logging.warning(f"Failed to generate index.html: {e}")


def _generate_index_html(
    snapshot_data: list,
    output_dir: str,
    run_config: dict | None = None,
    has_timeline_gif: bool = False,
) -> str:
    """Generate snapshot index for HTML report."""
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("snapshot_index.html.jinja")

    run_id = Path(output_dir).name
    total_clients = run_config.get("num_of_clients", "?") if run_config else "?"
    total_rounds = run_config.get("num_of_rounds", "?") if run_config else "?"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    unique_clients = sorted({s["client"] for s in snapshot_data})
    unique_rounds = sorted({s["round"] for s in snapshot_data})
    all_attack_types = []
    for s in snapshot_data:
        all_attack_types.extend(s["attack_types"])
    unique_attack_types = sorted(set(all_attack_types))

    context = {
        "run_id": run_id,
        "total_clients": total_clients,
        "total_rounds": total_rounds,
        "timestamp": timestamp,
        "snapshot_data": snapshot_data,
        "unique_clients": unique_clients,
        "unique_rounds": unique_rounds,
        "unique_attack_types": unique_attack_types,
        "has_timeline_gif": has_timeline_gif,
    }

    return template.render(context)


def generate_main_dashboard(output_dir: str) -> None:
    """Generate main dashboard for output directory.

    Creates a simple HTML dashboard that serves as an attack snapshot browser
    and quick navigation hub for all simulation outputs.

    Args:
        output_dir: Base output directory containing simulation outputs
    """
    output_path = Path(output_dir)
    if not output_path.exists():
        logging.warning(f"Output directory does not exist: {output_dir}")
        return

    # Scan directory for outputs
    run_id = output_path.name
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Find attack snapshot directories
    attack_snapshot_dirs = sorted(output_path.glob("attack_snapshots_*"))
    snapshot_info = []
    for snap_dir in attack_snapshot_dirs:
        strategy_num = snap_dir.name.split("_")[-1]
        index_html = snap_dir / "index.html"
        summary_json = snap_dir / "summary.json"

        num_clients = 0
        num_rounds = 0
        total_snapshots = 0

        if summary_json.exists():
            try:
                with open(summary_json) as f:
                    summary = json.load(f)
                    num_clients = len(summary.get("attack_timeline", {}))
                    timeline = summary.get("attack_timeline", {})
                    for client_rounds in timeline.values():
                        num_rounds = max(num_rounds, len(client_rounds))
                    total_snapshots = summary.get("attack_summary", {}).get("total_snapshots", 0)
            except Exception:
                pass

        snapshot_info.append(
            {
                "strategy_num": strategy_num,
                "dir_name": snap_dir.name,
                "has_index": index_html.exists(),
                "num_clients": num_clients,
                "num_rounds": num_rounds,
                "total_snapshots": total_snapshots,
            }
        )

    # Find plots (organized by category)
    all_plots = sorted(output_path.glob("*.pdf"))
    plot_categories: dict[str, list[str]] = {
        "Performance Metrics": [],
        "Attack Detection": [],
        "Client Analysis": [],
        "System Metrics": [],
    }

    for plot in all_plots:
        name = plot.name
        if any(x in name for x in ["accuracy", "loss", "average"]):
            plot_categories["Performance Metrics"].append(name)
        elif any(x in name for x in ["removal", "precision", "recall", "f1", "fp", "fn"]):
            plot_categories["Attack Detection"].append(name)
        elif any(x in name for x in ["distance", "criterion"]):
            plot_categories["Client Analysis"].append(name)
        elif any(x in name for x in ["time", "score_calculation"]):
            plot_categories["System Metrics"].append(name)
        else:
            plot_categories["Performance Metrics"].append(name)

    # Find CSV files
    csv_files = sorted(output_path.glob("csv/*.csv"))
    if not csv_files:
        csv_files = sorted(output_path.glob("*.csv"))

    # Find config files
    config_files = sorted(output_path.glob("config.json")) + sorted(
        output_path.glob("strategy_config_*.json")
    )

    # Generate HTML
    html_content = _generate_main_dashboard_html(
        run_id=run_id,
        timestamp=timestamp,
        snapshot_info=snapshot_info,
        plot_categories=plot_categories,
        csv_files=[f.relative_to(output_path).as_posix() for f in csv_files],
        config_files=[f.relative_to(output_path).as_posix() for f in config_files],
        termination=read_termination_summary(output_dir),
    )

    index_path = output_path / "index.html"
    try:
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logging.debug(f"Generated main dashboard: {index_path}")
    except Exception as e:
        logging.warning(f"Failed to generate main dashboard: {e}")


def _generate_main_dashboard_html(
    run_id: str,
    timestamp: str,
    snapshot_info: list,
    plot_categories: dict,
    csv_files: list,
    config_files: list,
    termination: dict | None = None,
) -> str:
    """Generate HTML content for main dashboard."""

    total_snapshots = sum(s["total_snapshots"] for s in snapshot_info)
    num_strategies = len(snapshot_info)

    termination_banner = ""
    if termination and termination.get("terminated_early"):
        round_num = termination.get("termination_round")
        reason = termination.get("termination_reason") or "early termination"
        termination_banner = (
            '<div style="background:#fff3cd;border:1px solid #ffc107;'
            "border-left:6px solid #ffc107;color:#7a5b00;padding:14px 20px;"
            'margin:0 0 20px;border-radius:6px;font-weight:600;">'
            f"⚠ This run terminated early at round {round_num} — {reason}"
            "</div>"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FL Simulation Results - {run_id}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
        }}
        .header h1 {{ font-size: 28px; margin-bottom: 10px; }}
        .header .meta {{ opacity: 0.9; font-size: 14px; }}
        .stats {{
            display: flex;
            gap: 20px;
            padding: 20px 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
            flex-wrap: wrap;
        }}
        .stat {{
            flex: 1;
            min-width: 150px;
            text-align: center;
            padding: 15px;
            background: white;
            border-radius: 6px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #667eea; }}
        .stat-label {{ font-size: 12px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 5px; }}
        .section {{
            padding: 30px;
            border-bottom: 1px solid #dee2e6;
        }}
        .section:last-child {{ border-bottom: none; }}
        .section-title {{
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 20px;
            color: #495057;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .snapshot-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 15px;
        }}
        .snapshot-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            border: 1px solid #dee2e6;
            transition: all 0.2s;
        }}
        .snapshot-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            border-color: #667eea;
        }}
        .snapshot-card h3 {{
            font-size: 16px;
            margin-bottom: 10px;
            color: #495057;
        }}
        .snapshot-card .info {{
            font-size: 13px;
            color: #6c757d;
            margin-bottom: 15px;
        }}
        .snapshot-card a {{
            display: inline-block;
            padding: 8px 16px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-size: 14px;
            font-weight: 500;
            transition: background 0.2s;
        }}
        .snapshot-card a:hover {{
            background: #5568d3;
        }}
        .file-list {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 10px;
        }}
        .file-item {{
            padding: 10px 15px;
            background: #f8f9fa;
            border-radius: 4px;
            font-size: 13px;
            color: #495057;
            border: 1px solid #dee2e6;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.2s;
        }}
        .file-item:hover {{
            background: #e9ecef;
            border-color: #667eea;
        }}
        .file-item a {{
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }}
        .file-item a:hover {{
            text-decoration: underline;
        }}
        .file-icon {{
            font-size: 16px;
            margin-right: 8px;
        }}
        .category-section {{
            margin-bottom: 25px;
        }}
        .category-title {{
            font-size: 16px;
            font-weight: 600;
            color: #495057;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 2px solid #dee2e6;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 FL Simulation Results</h1>
            <div class="meta">
                <strong>Run ID:</strong> {run_id} &nbsp;|&nbsp;
                <strong>Generated:</strong> {timestamp}
            </div>
        </div>

        {termination_banner}
        <div class="stats">
            <div class="stat">
                <div class="stat-value">{num_strategies}</div>
                <div class="stat-label">{"Strategy" if num_strategies == 1 else "Strategies"}</div>
            </div>
            <div class="stat">
                <div class="stat-value">{total_snapshots}</div>
                <div class="stat-label">Attack Snapshots</div>
            </div>
            <div class="stat">
                <div class="stat-value">{len([p for cat in plot_categories.values() for p in cat])}</div>
                <div class="stat-label">Plots Generated</div>
            </div>
            <div class="stat">
                <div class="stat-value">{len(csv_files)}</div>
                <div class="stat-label">Data Files</div>
            </div>
        </div>
"""

    # Attack Snapshots Section (primary focus)
    if snapshot_info:
        html += """
        <div class="section">
            <div class="section-title">🎯 Attack Snapshot Viewers</div>
            <div class="snapshot-grid">
"""
        for snap in snapshot_info:
            strategy_label = (
                f"Strategy {snap['strategy_num']}" if num_strategies > 1 else "Attack Snapshots"
            )
            html += f"""
                <div class="snapshot-card">
                    <h3>{strategy_label}</h3>
                    <div class="info">
                        {snap["total_snapshots"]} snapshots • {snap["num_clients"]} clients • {snap["num_rounds"]} rounds
                    </div>
                    <a href="{snap["dir_name"]}/index.html">Open Snapshot Browser →</a>
                </div>
"""
        html += """
            </div>
        </div>
"""

    # Plots Section
    total_plots = sum(len(plots) for plots in plot_categories.values())
    if total_plots > 0:
        html += """
        <div class="section">
            <div class="section-title">📈 Visualization Plots</div>
"""
        for category, plots in plot_categories.items():
            if plots:
                html += f"""
            <div class="category-section">
                <div class="category-title">{category}</div>
                <div class="file-list">
"""
                for plot in plots:
                    html += f"""
                    <div class="file-item">
                        <span><span class="file-icon">📊</span>{plot}</span>
                        <a href="{plot}" target="_blank">View</a>
                    </div>
"""
                html += """
                </div>
            </div>
"""
        html += """
        </div>
"""

    # Data Files Section
    if csv_files:
        html += """
        <div class="section">
            <div class="section-title">📂 Data Exports (CSV)</div>
            <div class="file-list">
"""
        for csv_file in csv_files:
            filename = Path(csv_file).name
            html += f"""
                <div class="file-item">
                    <span><span class="file-icon">📄</span>{filename}</span>
                    <a href="{csv_file}" download>Download</a>
                </div>
"""
        html += """
            </div>
        </div>
"""

    # Config Files Section
    if config_files:
        html += """
        <div class="section">
            <div class="section-title">⚙️ Strategy Configurations</div>
            <div class="file-list">
"""
        for config_file in config_files:
            filename = Path(config_file).name
            html += f"""
                <div class="file-item">
                    <span><span class="file-icon">📋</span>{filename}</span>
                    <a href="{config_file}" target="_blank">View</a>
                </div>
"""
        html += """
            </div>
        </div>
"""

    html += """
    </div>
</body>
</html>
"""

    return html
