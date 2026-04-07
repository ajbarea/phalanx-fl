---
title: Documentation
hide:
  - navigation
  - toc
  - footer
---

<div class="hero" markdown>

# <span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 8px; font-size: 1.2em;">scatter_plot</span> InteFL

**Federated learning execution & research framework**
{ .hero-subtitle }

<div class="hero-buttons" markdown>

[:octicons-rocket-24: Get Started](getting-started.md){ .md-button .md-button--primary }
[:octicons-book-24: Architecture](architecture.md){ .md-button }

</div>

<div class="hero-tagline" markdown>

<span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px;">shield</span> 9 Strategies | <span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px;">bug_report</span> 11 Attacks | <span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px;">database</span> 20+ Datasets
{ .hero-modes }

</div>

</div>

<div class="scroll-hint" aria-hidden="true">
  <div class="scroll-chevron"></div>
</div>

<section class="landing-section landing-section--intro">
  <div class="section-inner">
    <h2 class="section-title">What Is InteFL?</h2>
    <p class="section-lead">InteFL is a full-stack federated learning platform for running, attacking, and defending distributed ML simulations. Configure a JSON file, launch a simulation, and get CSV metrics, PDF plots, and attack snapshot reports &mdash; all orchestrated through a React dashboard or CLI.</p>
  </div>
</section>

<section class="landing-section landing-section--promise">
  <div class="section-inner">
    <h2 class="section-title">Configure. Simulate. Analyse.</h2>
    <p class="section-lead">Define your experiment in a single JSON config. InteFL handles dataset partitioning, client orchestration, adversarial injection, and results collection. Compare strategies side-by-side. Reproduce every run.<br><strong>Research-grade reproducibility, out of the box.</strong></p>
  </div>
</section>

<section class="landing-section">
  <div class="section-inner">
    <h2 class="section-title">One Config, Full Pipeline</h2>
    <div class="pipeline-flow">
      <div class="pipeline-step">
        <span class="step-icon material-symbols-outlined">data_object</span>
        <span class="step-label" style="color:#009688">Config</span>
      </div>
      <div class="pipeline-step">
        <span class="step-icon material-symbols-outlined">play_circle</span>
        <span class="step-label" style="color:#26A69A">Runner</span>
      </div>
      <div class="pipeline-step">
        <span class="step-icon material-symbols-outlined">scatter_plot</span>
        <span class="step-label" style="color:#4DB6AC">Simulation</span>
      </div>
      <div class="pipeline-step">
        <span class="step-icon material-symbols-outlined">shield</span>
        <span class="step-label" style="color:#7C4DFF">Strategy</span>
      </div>
      <div class="pipeline-step">
        <span class="step-icon material-symbols-outlined">group</span>
        <span class="step-label" style="color:#B388FF">Clients</span>
      </div>
      <div class="pipeline-step">
        <span class="step-icon material-symbols-outlined">trending_up</span>
        <span class="step-label" style="color:#CE93D8">Results</span>
      </div>
    </div>
    <p class="pipeline-caption">JSON config &rarr; partitioned datasets &rarr; N federated clients &rarr; aggregated metrics, plots, and snapshots</p>
  </div>
</section>

<section class="landing-section">
  <div class="section-inner">
    <h2 class="section-title">Explore the Docs</h2>
    <div class="feature-grid">
      <a href="getting-started/" class="feature-card" style="--card-accent: #009688">
        <span class="feature-icon material-symbols-outlined">rocket_launch</span>
        <div class="feature-name">Getting Started</div>
        <p>Install with Docker or locally and run your first simulation in minutes</p>
      </a>
      <a href="cli/" class="feature-card" style="--card-accent: #00897B">
        <span class="feature-icon material-symbols-outlined">terminal</span>
        <div class="feature-name">CLI Reference</div>
        <p>Every <code>intellifl-dev</code> command &mdash; setup, dev, test, lint, and more</p>
      </a>
      <a href="architecture/" class="feature-card" style="--card-accent: #26A69A">
        <span class="feature-icon material-symbols-outlined">account_tree</span>
        <div class="feature-name">Architecture</div>
        <p>How the API, Celery workers, Flower engine, and React UI fit together</p>
      </a>
      <a href="configuration/" class="feature-card" style="--card-accent: #4DB6AC">
        <span class="feature-icon material-symbols-outlined">settings</span>
        <div class="feature-name">Configuration</div>
        <p>Full StrategyConfig field reference &mdash; every knob you can turn</p>
      </a>
      <a href="datasets/" class="feature-card" style="--card-accent: #7C4DFF">
        <span class="feature-icon material-symbols-outlined">database</span>
        <div class="feature-name">Datasets</div>
        <p>FEMNIST, FLAIR, MedMNIST, CIFAR-100, HuggingFace text, and more</p>
      </a>
      <a href="strategies/" class="feature-card" style="--card-accent: #651FFF">
        <span class="feature-icon material-symbols-outlined">shield</span>
        <div class="feature-name">Strategies</div>
        <p>FedAvg, Krum, Multi-Krum, Bulyan, RFA, PID, Trust, Trimmed Mean, ArKrum</p>
      </a>
      <a href="attacks/" class="feature-card" style="--card-accent: #B388FF">
        <span class="feature-icon material-symbols-outlined">bug_report</span>
        <div class="feature-name">Attacks</div>
        <p>Label flipping, backdoors, model poisoning, Byzantine perturbation, and more</p>
      </a>
      <a href="api/" class="feature-card" style="--card-accent: #CE93D8">
        <span class="feature-icon material-symbols-outlined">api</span>
        <div class="feature-name">API Reference</div>
        <p>REST endpoints for launching, monitoring, and managing simulations</p>
      </a>
    </div>
  </div>
</section>

<section class="landing-section">
  <div class="section-inner">
    <h2 class="section-title">Key Features</h2>
    <div class="feature-grid feature-grid--compact">
      <div class="feature-card feature-card--flat">
        <div class="feature-name"><span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px;">verified_user</span> 9 Aggregation Strategies</div>
        <p>FedAvg, Krum, Multi-Krum, Bulyan, RFA, Trimmed Mean, PID-based, Trust-based, ArKrum &mdash; each with configurable parameters</p>
      </div>
      <div class="feature-card feature-card--flat">
        <div class="feature-name"><span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px;">warning</span> 11 Attack Types</div>
        <p><strong>Data poisoning:</strong> label flipping, targeted label flipping, Gaussian noise, backdoor triggers, token replacement<br><strong>Model poisoning:</strong> model poisoning, gradient scaling, boosted scaling, Byzantine perturbation, inner product manipulation, alternating min</p>
      </div>
      <div class="feature-card feature-card--flat">
        <div class="feature-name"><span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px;">photo_library</span> Rich Dataset Support</div>
        <p>FEMNIST, FLAIR, CIFAR-100, 11 MedMNIST subsets, Lung Cancer, plus HuggingFace text datasets (financial, legal, medical)</p>
      </div>
      <div class="feature-card feature-card--flat">
        <div class="feature-name"><span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px;">layers</span> Full-Stack Platform</div>
        <p>REST API + React dashboard, Celery task queue, SSE live streaming, Docker Compose deployment, and this docs site &mdash; all included</p>
      </div>
    </div>
  </div>
</section>

<section class="landing-section">
  <div class="section-inner">
    <h2 class="section-title">Technology Stack</h2>
    <div class="tech-stack">
      <div class="tech-item"><strong><span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px; font-size: 1.1em;">psychology</span> FL</strong> Flower (flwr)</div>
      <div class="tech-item"><strong><span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px; font-size: 1.1em;">bolt</span> Compute</strong> Ray</div>
      <div class="tech-item"><strong><span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px; font-size: 1.1em;">local_fire_department</span> DL</strong> PyTorch</div>
      <div class="tech-item"><strong><span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px; font-size: 1.1em;">smart_toy</span> LLM</strong> HuggingFace + PEFT</div>
      <div class="tech-item"><strong><span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px; font-size: 1.1em;">api</span> API</strong> FastAPI + Uvicorn</div>
      <div class="tech-item"><strong><span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px; font-size: 1.1em;">inbox</span> Queue</strong> Celery + Redis</div>
      <div class="tech-item"><strong><span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px; font-size: 1.1em;">code</span> UI</strong> React + Vite</div>
      <div class="tech-item"><strong><span class="material-symbols-outlined" style="vertical-align: middle; margin-right: 4px; font-size: 1.1em;">menu_book</span> Docs</strong> Zensical</div>
    </div>
  </div>
</section>

<section class="landing-section cta-section">
  <div class="section-inner">
    <h2 class="section-title">Ready to Simulate?</h2>
    <p class="cta-lead">Configure. Launch. Defend. Analyse.</p>
    <a href="getting-started/" class="md-button md-button--primary cta-button">Get Started</a>
  </div>
</section>

<footer class="landing-footer">
  <span>AJ Barea &middot; 2026</span>
  <a href="https://github.com/ajbarea/phalanx-fl" aria-label="GitHub">
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
  </a>
</footer>
