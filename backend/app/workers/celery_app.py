"""Celery application — distributed background jobs (AI summary, quiz timers,
attendance reconcile, recording ingest).

Run a worker:  celery -A app.workers.celery_app worker --loglevel=info
Run the beat:  celery -A app.workers.celery_app beat   --loglevel=info

Task modules are added to `include` as they are built. Handlers must be
idempotent (jobs can be retried).
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "linkhq",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.quiz_tasks"],  # more added per feature
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
)
