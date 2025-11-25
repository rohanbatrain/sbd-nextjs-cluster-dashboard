#!/bin/bash
set -e

# Entrypoint script for Second Brain Database Docker container
# Supports multiple run modes: api, celery-worker, celery-beat

MODE="${1:-api}"

echo "Starting Second Brain Database in mode: $MODE"

case "$MODE" in
  api)
    echo "Starting FastAPI application..."
    exec uvicorn src.second_brain_database.main:app \
      --host 0.0.0.0 \
      --port 8000 \
      --workers ${UVICORN_WORKERS:-4} \
      --proxy-headers \
      --forwarded-allow-ips "*"
    ;;
    
  celery-worker)
    echo "Starting Celery worker..."
    exec celery -A src.second_brain_database.tasks.celery_app:celery_app worker \
      --loglevel=${CELERY_LOG_LEVEL:-info} \
      --concurrency=${CELERY_WORKER_CONCURRENCY:-4} \
      --max-tasks-per-child=${CELERY_MAX_TASKS_PER_CHILD:-1000} \
      --task-events \
      --without-gossip \
      --without-mingle
    ;;
    
  celery-beat)
    echo "Starting Celery beat scheduler..."
    exec celery -A src.second_brain_database.tasks.celery_app:celery_app beat \
      --loglevel=${CELERY_LOG_LEVEL:-info} \
      --pidfile=/tmp/celerybeat.pid \
      --schedule=/tmp/celerybeat-schedule
    ;;
    
  *)
    echo "Unknown mode: $MODE"
    echo "Available modes: api, celery-worker, celery-beat"
    exit 1
    ;;
esac
