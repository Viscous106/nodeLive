# syntax=docker/dockerfile:1
#
# Single-image deploy: the frontend is built and bundled into the backend image,
# which serves the SPA + API + WebSocket on one origin (no cross-site cookies).
# Same image runs the web process and the Celery worker (see fly.toml processes).

# --- Stage 1: build the React/Vite frontend ---------------------------------
FROM node:22-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build                      # tsc -b && vite build → /fe/dist

# --- Stage 2: Python backend + bundled SPA ----------------------------------
FROM python:3.12-slim AS app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/ ./
COPY --from=frontend /fe/dist ./static
ENV FRONTEND_DIST=/app/static
RUN chmod +x start.sh

EXPOSE 8080
# start.sh = migrate + Celery worker + web server (Render uses this).
# fly.toml overrides it with separate web/worker process commands.
CMD ["sh", "start.sh"]
