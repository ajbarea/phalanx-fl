"""Celery application configuration for FL simulation task queue.

Redis broker handles task distribution; workers execute simulations sequentially
to protect GPU resources. Flower (a celery-monitor NOT flwr.ai) provides web dashboard.

Broker: redis://localhost:6379/0
Backend: redis://localhost:6379/1

Usage:
    celery -A intellifl.celery_app worker --loglevel=info --concurrency=1
    celery -A intellifl.celery_app flower --port=5555
"""

import os

from celery import Celery

# Broker and backend URLs are sourced from env vars for containerized deployments,
# with a default to localhost for local development.
BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
BACKEND_URL = os.environ.get("CELERY_RESULT_BACKEND_URL", "redis://localhost:6379/1")

app = Celery(
    "fl_execution_framework",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=["intellifl.tasks.simulation_tasks"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,  # Required for accurate status tracking
    worker_prefetch_multiplier=1,  # Sequential execution (GPU protection)
    task_acks_late=True,  # Don't ack until task completes (crash recovery)
    task_reject_on_worker_lost=True,  # Requeue if worker dies mid-task
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks (memory protection)
    broker_pool_limit=10,  # Max connections to Redis broker
    # research(2026-05): hard + soft task timeouts protect against jobs that
    # hang indefinitely (broken aggregator, infinite loop in attack code,
    # GPU OOM with a stuck recovery). Soft (6900s = 1h55m) raises
    # `SoftTimeLimitExceeded` so the task can clean up + write a `failed`
    # status; hard (7200s = 2h) `SIGKILL`s if cleanup itself hangs. Real
    # FL runs in this codebase top out around 60-90 min wall time on the
    # large-tier baselines, so 2h is comfortably above legitimate work.
    task_time_limit=7200,
    task_soft_time_limit=6900,
)
