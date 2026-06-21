#!/bin/sh
# Container start (used by the deploy image): run migrations, start the Celery
# worker in the background (Render's free tier has no separate worker service),
# then exec the web server in the foreground so it owns PID 1 for signals.
#
# Memory: the free tier caps at 512MB. The worker uses a single-process `solo`
# pool (the default prefork pool forks one child per CPU → multiplies RAM) and
# RUN_WORKER=0 disables it entirely if the box still OOMs. The web server keeps
# one worker. For real load, move to a paid plan + a dedicated worker service.
set -e

alembic upgrade head
# Seed in the background so the web port opens immediately — Render's port scan
# doesn't wait on seeding, and a seed hiccup can't block the service coming up.
python -m scripts.seed &
if [ "${RUN_WORKER:-1}" != "0" ]; then
  celery -A app.workers.celery_app worker --pool=solo --concurrency=1 \
    --loglevel=warning &
fi
exec uvicorn app.main:socket_app --host 0.0.0.0 --port "${PORT:-8080}"
