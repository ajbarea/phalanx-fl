---
title: Phalanx
description: Federated learning on the latest Flower, with OpenTelemetry-native observability.
hide:
  - navigation
  - toc
  - footer
---

<div class="hero" markdown>

# <span class="hero-mark material-symbols-outlined" aria-hidden="true">scatter_plot</span><span class="hero-wordmark">Phalanx</span>

Federated learning on the latest Flower, with OpenTelemetry-native observability.
{ .hero-subtitle }

<div class="hero-buttons" markdown>

[:octicons-rocket-24: Get started](getting-started.md){ .md-button .md-button--primary }
[:octicons-book-24: Architecture](architecture.md){ .md-button }

</div>

<div class="hero-modes">
  <span class="hero-chip"><span class="material-symbols-outlined" aria-hidden="true">hub</span>flwr 1.36 Message API</span>
  <span class="hero-chip"><span class="material-symbols-outlined" aria-hidden="true">tune</span>Federated LoRA</span>
  <span class="hero-chip"><span class="material-symbols-outlined" aria-hidden="true">monitoring</span>OTel traces and metrics</span>
</div>

</div>

<div class="scroll-hint" aria-hidden="true">
  <div class="scroll-chevron"></div>
</div>

<section class="landing-section">
  <div class="section-inner">
    <span class="section-eyebrow">What is Phalanx?</span>
    <h2 class="section-title">A federated run you can watch, round by round</h2>
    <p class="section-lead">A federated-learning research testbed on the latest Flower release. Every round emits a server span and FL metrics, every client a span for its train and evaluate pass, so the whole run shows up in <strong>Jaeger</strong>, <strong>Grafana Tempo</strong> or any <strong>OpenTelemetry Collector</strong>.</p>
  </div>
</section>

<section class="landing-section landing-section--alt">
  <div class="section-inner">
    <span class="section-eyebrow">How it works</span>
    <h2 class="section-title">One federated round, traced end to end</h2>
    <ol class="pipeline-flow">
      <li class="pipeline-step">
        <span class="step-icon material-symbols-outlined" aria-hidden="true">send</span>
        <span class="step-label">Broadcast</span>
        <span class="step-detail">Adapters go to sampled clients</span>
      </li>
      <li class="pipeline-step">
        <span class="step-icon material-symbols-outlined" aria-hidden="true">tune</span>
        <span class="step-label">Train</span>
        <span class="step-detail">Each client fine-tunes LoRA on its partition</span>
      </li>
      <li class="pipeline-step" style="--step-accent: var(--phx-violet)">
        <span class="step-icon material-symbols-outlined" aria-hidden="true">merge</span>
        <span class="step-label">Aggregate</span>
        <span class="step-detail">FedAvg over the returned adapters</span>
      </li>
      <li class="pipeline-step" style="--step-accent: var(--phx-violet)">
        <span class="step-icon material-symbols-outlined" aria-hidden="true">insights</span>
        <span class="step-label">Evaluate</span>
        <span class="step-detail">On client holdouts and the global test split</span>
      </li>
      <li class="pipeline-step">
        <span class="step-icon material-symbols-outlined" aria-hidden="true">monitoring</span>
        <span class="step-label">Trace</span>
        <span class="step-detail">A round span with client spans as children</span>
      </li>
      <li class="pipeline-step">
        <span class="step-icon material-symbols-outlined" aria-hidden="true">cell_tower</span>
        <span class="step-label">Export</span>
        <span class="step-detail">OTLP, console, or in-memory for tests</span>
      </li>
    </ol>
    <p class="pipeline-caption">Only the LoRA adapters and the classification head are federated. The frozen backbone never leaves a client.</p>
  </div>
</section>

<section class="landing-section">
  <div class="section-inner">
    <span class="section-eyebrow">The default showcase</span>
    <h2 class="section-title">Sentiment, federated, on a laptop</h2>
    <div class="spec-grid">
      <div class="spec">
        <span class="spec-key">Model</span>
        <span class="spec-value">Tiny BERT with LoRA</span>
        <span class="spec-note"><code>google/bert_uncased_L-2_H-128_A-2</code></span>
      </div>
      <div class="spec">
        <span class="spec-key">Data</span>
        <span class="spec-value">IMDB sentiment</span>
        <span class="spec-note">Partitioned non-IID with a Dirichlet partitioner</span>
      </div>
      <div class="spec">
        <span class="spec-key">Federation</span>
        <span class="spec-value">Five simulated nodes</span>
        <span class="spec-note">Reproduced from a clone with no bootstrap step</span>
      </div>
      <div class="spec">
        <span class="spec-key">Hardware</span>
        <span class="spec-value">CPU is enough</span>
        <span class="spec-note">No GPU required</span>
      </div>
    </div>
    <div class="stack-row">
      <span class="stack-chip">Flower 1.36</span>
      <span class="stack-chip">flwr-datasets</span>
      <span class="stack-chip">HuggingFace Transformers</span>
      <span class="stack-chip">PEFT / LoRA</span>
      <span class="stack-chip">OpenTelemetry</span>
      <span class="stack-chip">uv</span>
    </div>
  </div>
</section>

<section class="landing-section landing-section--alt">
  <div class="section-inner">
    <span class="section-eyebrow">Explore</span>
    <h2 class="section-title">Start here</h2>
    <div class="feature-grid">
      <a href="getting-started/" class="feature-card">
        <span class="feature-icon material-symbols-outlined" aria-hidden="true">rocket_launch</span>
        <span class="feature-name">Getting started</span>
        <p>Install, run your first federated simulation, and print its OpenTelemetry traces.</p>
        <span class="feature-go">Run a simulation &rarr;</span>
      </a>
      <a href="architecture/" class="feature-card">
        <span class="feature-icon material-symbols-outlined" aria-hidden="true">account_tree</span>
        <span class="feature-name">Architecture</span>
        <p>How <code>task</code>, <code>client_app</code>, <code>server_app</code> and the telemetry layer fit the Flower app model.</p>
        <span class="feature-go">Read the design &rarr;</span>
      </a>
      <a href="research/" class="feature-card" style="--card-accent: var(--phx-violet)">
        <span class="feature-icon material-symbols-outlined" aria-hidden="true">science</span>
        <span class="feature-name">Research</span>
        <p>Lineage and positioning, including the RIT InteFL capstone it grew out of.</p>
        <span class="feature-go">See the work &rarr;</span>
      </a>
    </div>
  </div>
</section>

<footer class="landing-footer">
  <span>2026 <img src="assets/brand.png" alt="" aria-hidden="true" class="brand-mark"> AJ Barea</span>
  <a href="https://github.com/ajbarea/phalanx-fl" aria-label="Phalanx-FL on GitHub">
    <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
  </a>
</footer>
