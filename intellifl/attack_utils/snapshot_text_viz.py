"""
Text visualization utilities for attack snapshots.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import numpy as np


def _extract_attack_param(
    attack_config: dict | list[dict], *attack_parameters: str, default: Any = "?"
) -> Any:
    """Extract first matching parameter from attack config."""
    config = (
        attack_config[0] if isinstance(attack_config, list) and attack_config else attack_config
    )

    if isinstance(config, dict):
        for attack_parameter in attack_parameters:
            if attack_parameter in config:
                return config[attack_parameter]

    return default


def _extract_attack_type(attack_config: dict | list[dict]) -> str:
    """Extract attack type string from config, joining multiple with underscore."""
    if isinstance(attack_config, list):
        if attack_config:
            attack_types = [
                cfg.get("attack_type") or cfg.get("type", "unknown") for cfg in attack_config
            ]
            return "_".join(attack_types)
        else:
            return "unknown"
    else:
        return attack_config.get("attack_type") or attack_config.get("type", "unknown")


def save_text_samples(
    labels: np.ndarray,
    original_labels: np.ndarray,
    filepath: Path,
    attack_config: dict | list[dict] | None = None,
    tokenizer=None,
    input_ids_original: np.ndarray | None = None,
    input_ids_poisoned: np.ndarray | None = None,
) -> None:
    """Save text attack samples to a plain text visualization file.

    Args:
        labels: Poisoned labels array.
        original_labels: Original labels array before attack.
        filepath: Output file path.
        attack_config: Attack configuration dict or list of dicts (optional).
        tokenizer: HuggingFace tokenizer for decoding tokens (optional).
        input_ids_original: Original token IDs before poisoning (optional).
        input_ids_poisoned: Poisoned token IDs (optional).
    """
    with open(filepath, "w", encoding="utf-8") as f:
        if (
            tokenizer is not None
            and input_ids_original is not None
            and input_ids_poisoned is not None
        ):
            f.write("=" * 80 + "\n")
            f.write("TOKEN REPLACEMENT ATTACK VISUALIZATION\n")
            f.write("=" * 80 + "\n\n")

            if attack_config:
                attack_type = _extract_attack_type(attack_config)
                f.write(f"Attack Type: {attack_type}\n")

                if attack_type == "token_replacement":
                    target_vocab = _extract_attack_param(
                        attack_config, "target_vocabulary", default="unknown"
                    )
                    replacement_strategy = _extract_attack_param(
                        attack_config, "replacement_strategy", default="negative"
                    )
                    replacement_prob = _extract_attack_param(
                        attack_config, "replacement_probability", default=1.0
                    )

                    f.write(f"Target Vocabulary: {target_vocab}\n")
                    f.write(f"Replacement Strategy: {replacement_strategy}\n")
                    f.write(f"Replacement Probability: {replacement_prob}\n")

                f.write("\n" + "=" * 80 + "\n\n")

            samples_shown = 0
            samples_skipped = 0

            for i in range(len(labels)):
                original_tokens = input_ids_original[i]
                poisoned_tokens = input_ids_poisoned[i]

                try:
                    original_text = tokenizer.decode(original_tokens, skip_special_tokens=True)
                    poisoned_text = tokenizer.decode(poisoned_tokens, skip_special_tokens=True)

                    if original_text == poisoned_text:
                        samples_skipped += 1
                        continue

                    f.write(f"--- Sample {i} ---\n\n")

                    f.write(f'ORIGINAL: "{original_text}"\n')
                    f.write(f'POISONED: "{poisoned_text}"\n')

                    num_replaced = np.sum(original_tokens != poisoned_tokens)
                    total_tokens = len(original_tokens)
                    replacement_rate = num_replaced / total_tokens * 100 if total_tokens > 0 else 0

                    f.write(
                        f"          {num_replaced}/{total_tokens} tokens replaced ({replacement_rate:.1f}%)\n"
                    )
                    f.write("          " + "^" * 15 + "[REPLACED]" + "^" * 15 + "\n")

                    current_label = labels[i]
                    original_label = original_labels[i]

                    if isinstance(current_label, np.ndarray) and current_label.size > 1:
                        label_changed = not np.array_equal(current_label, original_label)
                        num_masked_original = np.sum(original_label != -100)
                        num_masked_current = np.sum(current_label != -100)

                        if label_changed:
                            f.write(
                                f"Labels: {num_masked_original} masked tokens → {num_masked_current} masked tokens (CHANGED)\n"
                            )
                        else:
                            f.write(f"Labels: {num_masked_original} masked tokens (unchanged)\n")
                    else:
                        if np.array_equal(current_label, original_label):
                            f.write(f"Label: {current_label} (unchanged)\n")
                        else:
                            f.write(f"Label: {original_label} → {current_label} (FLIPPED)\n")

                    samples_shown += 1

                except Exception as e:
                    f.write(f"--- Sample {i} ---\n\n")
                    f.write(f"[Decoding error: {e}]\n")
                    f.write(f"Original token IDs (first 10): {original_tokens[:10].tolist()}\n")
                    f.write(f"Poisoned token IDs (first 10): {poisoned_tokens[:10].tolist()}\n")
                    samples_shown += 1

                f.write("\n")

            if samples_skipped > 0:
                f.write("=" * 80 + "\n")
                f.write(
                    f"SUMMARY: {samples_shown} samples modified, {samples_skipped} samples unchanged (skipped)\n"
                )
                f.write("=" * 80 + "\n")
        else:
            f.write("Sample Labels (Poisoned vs Original)\n")
            f.write("=" * 40 + "\n")
            for i, (label, orig) in enumerate(zip(labels, original_labels, strict=False)):
                f.write(f"Sample {i}: {label} (was {orig})\n")


def save_text_samples_html(
    labels: np.ndarray,
    original_labels: np.ndarray,
    filepath: Path,
    attack_config: dict | list[dict] | None = None,
    tokenizer=None,
    input_ids_original: np.ndarray | None = None,
    input_ids_poisoned: np.ndarray | None = None,
) -> None:
    """Saves text attack samples to an HTML file with syntax-highlighted diff.

    Creates a visual HTML representation with:
    - Token-level highlighting (red for replaced, green for original)
    - Side-by-side comparison of original and poisoned text
    - Interactive collapsible sections for each sample
    - Summary statistics

    Args:
        labels: The poisoned labels array.
        original_labels: The original labels array.
        filepath: The output HTML file path.
        attack_config: The attack configuration dictionary or list of dictionaries.
        tokenizer: The tokenizer for decoding token IDs.
        input_ids_original: The original token IDs.
        input_ids_poisoned: The poisoned token IDs.
    """
    # HTML template with embedded CSS
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Token Replacement Attack Visualization</title>
    <style>
        :root {{
            --bg-color: #1e1e1e;
            --card-bg: #2d2d2d;
            --text-color: #e0e0e0;
            --border-color: #404040;
            --original-bg: #1a3d1a;
            --replaced-bg: #4d1a1a;
            --unchanged-bg: #2d2d2d;
            --header-bg: #0d47a1;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            color: #fff;
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, var(--header-bg), #1565c0);
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .config-box {{
            background-color: var(--card-bg);
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid var(--header-bg);
        }}
        .config-box h3 {{
            margin-top: 0;
            color: #90caf9;
        }}
        .config-item {{
            display: inline-block;
            margin-right: 20px;
            padding: 5px 10px;
            background: rgba(255,255,255,0.05);
            border-radius: 4px;
        }}
        .summary-box {{
            background-color: var(--card-bg);
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }}
        .summary-stat {{
            text-align: center;
            padding: 10px 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            min-width: 100px;
        }}
        .summary-stat .value {{
            font-size: 24px;
            font-weight: bold;
            color: #90caf9;
        }}
        .summary-stat .label {{
            font-size: 12px;
            opacity: 0.8;
        }}
        .sample-card {{
            background-color: var(--card-bg);
            border-radius: 8px;
            margin-bottom: 15px;
            overflow: hidden;
            border: 1px solid var(--border-color);
        }}
        .sample-header {{
            padding: 12px 20px;
            background: rgba(255,255,255,0.05);
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .sample-header:hover {{
            background: rgba(255,255,255,0.1);
        }}
        .sample-title {{
            font-weight: bold;
        }}
        .sample-stats {{
            font-size: 14px;
            opacity: 0.8;
        }}
        .sample-content {{
            padding: 20px;
        }}
        .text-columns {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }}
        .text-column {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        .text-label {{
            font-weight: bold;
            font-size: 13px;
        }}
        .text-label.original-label {{
            color: #66bb6a;
        }}
        .text-label.poisoned-label {{
            color: #ef5350;
        }}
        .text-content {{
            font-family: 'Consolas', 'Monaco', monospace;
            padding: 12px;
            border-radius: 6px;
            white-space: pre-wrap;
            word-break: break-word;
            line-height: 1.8;
            flex: 1;
        }}
        .original-text {{
            background-color: var(--original-bg);
            border: 1px solid #2e7d32;
        }}
        .poisoned-text {{
            background-color: var(--replaced-bg);
            border: 1px solid #c62828;
        }}
        @media (max-width: 480px) {{
            .text-columns {{
                grid-template-columns: 1fr;
            }}
        }}
        .token {{
            display: inline;
            padding: 2px 4px;
            margin: 1px;
            border-radius: 3px;
        }}
        .token-original {{
            background-color: #2e7d32;
            color: #c8e6c9;
        }}
        .token-replaced {{
            background-color: #c62828;
            color: #ffcdd2;
        }}
        .token-unchanged {{
            opacity: 0.7;
        }}
        .diff-legend {{
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            padding: 10px;
            background: rgba(255,255,255,0.05);
            border-radius: 6px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 4px;
        }}
        .legend-original {{ background-color: #2e7d32; }}
        .legend-replaced {{ background-color: #c62828; }}
        .label-change {{
            margin-top: 10px;
            padding: 8px 12px;
            background: rgba(255,255,255,0.05);
            border-radius: 4px;
            font-size: 14px;
        }}
        details > summary {{
            list-style: none;
        }}
        details > summary::-webkit-details-marker {{
            display: none;
        }}
        details[open] .sample-header {{
            border-bottom: 1px solid var(--border-color);
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Token Replacement Attack Visualization</h1>
        {config_section}
        <div class="diff-legend">
            <div class="legend-item">
                <div class="legend-color legend-original"></div>
                <span>Original Token</span>
            </div>
            <div class="legend-item">
                <div class="legend-color legend-replaced"></div>
                <span>Replaced Token</span>
            </div>
        </div>
        {summary_section}
        {samples_section}
    </div>
</body>
</html>"""

    samples_html = []
    total_replaced = 0
    total_tokens = 0
    samples_modified = 0
    samples_unchanged = 0

    if tokenizer is not None and input_ids_original is not None and input_ids_poisoned is not None:
        for i in range(len(labels)):
            original_tokens = input_ids_original[i]
            poisoned_tokens = input_ids_poisoned[i]

            try:
                # Decode full texts
                original_text = tokenizer.decode(original_tokens, skip_special_tokens=True)
                poisoned_text = tokenizer.decode(poisoned_tokens, skip_special_tokens=True)

                if original_text == poisoned_text:
                    samples_unchanged += 1
                    continue

                samples_modified += 1

                # Token-by-token comparison
                original_html_tokens = []
                poisoned_html_tokens = []

                # Get individual token strings for highlighting
                for _j, (orig_id, pois_id) in enumerate(
                    zip(original_tokens, poisoned_tokens, strict=False)
                ):
                    orig_token_str = tokenizer.decode([orig_id])
                    pois_token_str = tokenizer.decode([pois_id])

                    if orig_id != pois_id:
                        total_replaced += 1
                        original_html_tokens.append(
                            f'<span class="token token-original">{html.escape(orig_token_str)}</span>'
                        )
                        poisoned_html_tokens.append(
                            f'<span class="token token-replaced">{html.escape(pois_token_str)}</span>'
                        )
                    else:
                        original_html_tokens.append(
                            f'<span class="token token-unchanged">{html.escape(orig_token_str)}</span>'
                        )
                        poisoned_html_tokens.append(
                            f'<span class="token token-unchanged">{html.escape(pois_token_str)}</span>'
                        )
                    total_tokens += 1

                num_replaced = np.sum(original_tokens != poisoned_tokens)
                replacement_rate = (
                    num_replaced / len(original_tokens) * 100 if len(original_tokens) > 0 else 0
                )

                # Label change info
                current_label = labels[i]
                original_label = original_labels[i]
                label_html = ""

                if isinstance(current_label, np.ndarray) and current_label.size > 1:
                    label_changed = not np.array_equal(current_label, original_label)
                    num_masked_original = np.sum(original_label != -100)
                    num_masked_current = np.sum(current_label != -100)
                    if label_changed:
                        label_html = f'<div class="label-change">Labels: {num_masked_original} masked tokens &rarr; {num_masked_current} masked tokens (CHANGED)</div>'
                    else:
                        label_html = f'<div class="label-change">Labels: {num_masked_original} masked tokens (unchanged)</div>'
                else:
                    if not np.array_equal(current_label, original_label):
                        label_html = f'<div class="label-change">Label: {original_label} &rarr; {current_label} (FLIPPED)</div>'

                sample_html = f"""
        <details class="sample-card" open>
            <summary class="sample-header">
                <span class="sample-title">Sample {i}</span>
                <span class="sample-stats">{num_replaced} tokens replaced ({replacement_rate:.1f}%)</span>
            </summary>
            <div class="sample-content">
                <div class="text-columns">
                    <div class="text-column">
                        <div class="text-label original-label">Original:</div>
                        <div class="text-content original-text">{"".join(original_html_tokens)}</div>
                    </div>
                    <div class="text-column">
                        <div class="text-label poisoned-label">Poisoned:</div>
                        <div class="text-content poisoned-text">{"".join(poisoned_html_tokens)}</div>
                    </div>
                </div>
                {label_html}
            </div>
        </details>"""
                samples_html.append(sample_html)

            except Exception as e:
                sample_html = f"""
        <details class="sample-card">
            <summary class="sample-header">
                <span class="sample-title">Sample {i}</span>
                <span class="sample-stats">Decoding error</span>
            </summary>
            <div class="sample-content">
                <p>Error: {html.escape(str(e))}</p>
                <p>Original token IDs (first 10): {original_tokens[:10].tolist()}</p>
                <p>Poisoned token IDs (first 10): {poisoned_tokens[:10].tolist()}</p>
            </div>
        </details>"""
                samples_html.append(sample_html)
                samples_modified += 1

    # Build config section
    config_html = ""
    if attack_config:
        attack_type = _extract_attack_type(attack_config)
        config_items = [f'<span class="config-item">Attack: {attack_type}</span>']

        if attack_type == "token_replacement":
            target_vocab = _extract_attack_param(
                attack_config, "target_vocabulary", default="unknown"
            )
            replacement_strategy = _extract_attack_param(
                attack_config, "replacement_strategy", default="negative"
            )
            replacement_prob = _extract_attack_param(
                attack_config, "replacement_probability", default=1.0
            )
            config_items.extend(
                [
                    f'<span class="config-item">Target: {target_vocab}</span>',
                    f'<span class="config-item">Strategy: {replacement_strategy}</span>',
                    f'<span class="config-item">Probability: {replacement_prob}</span>',
                ]
            )

        config_html = f"""
        <div class="config-box">
            <h3>Attack Configuration</h3>
            {"".join(config_items)}
        </div>"""

    # Build summary section
    replacement_pct = (total_replaced / total_tokens * 100) if total_tokens > 0 else 0
    summary_html = f"""
        <div class="summary-box">
            <div class="summary-stat">
                <div class="value">{samples_modified}</div>
                <div class="label">Samples Modified</div>
            </div>
            <div class="summary-stat">
                <div class="value">{samples_unchanged}</div>
                <div class="label">Unchanged</div>
            </div>
            <div class="summary-stat">
                <div class="value">{total_replaced}</div>
                <div class="label">Tokens Replaced</div>
            </div>
            <div class="summary-stat">
                <div class="value">{replacement_pct:.1f}%</div>
                <div class="label">Replacement Rate</div>
            </div>
        </div>"""

    # Generate final HTML
    final_html = html_template.format(
        config_section=config_html,
        summary_section=summary_html,
        samples_section="\n".join(samples_html),
    )

    # Ensure filepath has .html extension
    filepath = Path(filepath)
    if filepath.suffix != ".html":
        filepath = filepath.with_suffix(".html")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(final_html)
