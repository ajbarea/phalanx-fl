---
title: Documentation
hide:
  - navigation
  - toc
  - footer
---

<div class="hero" markdown>

# <span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 8px; font-size: 1.2em;">scatter_plot</span> Phalanx

**Federated learning on the latest Flower, with OpenTelemetry-native observability**
{ .hero-subtitle }

<div class="hero-buttons" markdown>

[:octicons-rocket-24: Get Started](getting-started.md){ .md-button .md-button--primary }
[:octicons-book-24: Architecture](architecture.md){ .md-button }

</div>

<div class="hero-tagline" markdown>

<span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px;">hub</span> flwr 1.31 Message API | <span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px;">tune</span> federated LoRA | <span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px;">monitoring</span> OTel traces + metrics
{ .hero-modes }

</div>

</div>

## What is Phalanx?

Phalanx is a federated-learning research testbed that rides the **latest** Flower
release: the `flwr` Message API, `flwr-datasets`, HuggingFace Transformers, and
PEFT/LoRA. Its distinguishing feature is **OpenTelemetry-native observability** —
the server emits a span and FL metrics for every round, and each client emits a
span for its local train/evaluate pass, so a federated run is visible in any OTLP
backend (Jaeger, Grafana Tempo, an OpenTelemetry Collector).

The default showcase is a federated **LoRA** fine-tune of a tiny BERT on IMDB
sentiment, partitioned non-IID with a Dirichlet partitioner. Only the LoRA adapters
and the classification head are federated; the frozen backbone stays on each client.

## Explore

<div class="feature-grid">

<a href="getting-started/" class="feature-card" style="--card-accent: #009688">
<span class="feature-icon material-symbols-outlined">rocket_launch</span>
<div class="feature-name">Getting Started</div>
<p>Install, run your first federated simulation, and wire up OpenTelemetry traces.</p>
</a>

<a href="architecture/" class="feature-card" style="--card-accent: #26A69A">
<span class="feature-icon material-symbols-outlined">account_tree</span>
<div class="feature-name">Architecture</div>
<p>How <code>task</code>, <code>client_app</code>, <code>server_app</code>, and the telemetry layer fit the Flower app-model.</p>
</a>

<a href="research/" class="feature-card" style="--card-accent: #7C4DFF">
<span class="feature-icon material-symbols-outlined">science</span>
<div class="feature-name">Research</div>
<p>Lineage and positioning, including the RIT IntelliFL capstone origin.</p>
</a>

</div>
