#!/bin/sh
# Container start (used by the deploy image): run migrations, start the Celery
# worker in the background (Render's free tier has no separate worker service),
# then exec the web server in the foreground so it owns PID 1 for signals.
set -e

alembic upgrade head
celery -A app.workers.celery_app worker --loglevel=info &
exec uvicorn app.main:socket_app --host 0.0.0.0 --port "${PORT:-8080}"
