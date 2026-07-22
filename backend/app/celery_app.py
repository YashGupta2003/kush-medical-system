"""
Celery app instance. The API process (FastAPI/uvicorn) and the worker
process (celery worker) both import this same `celery_app` object, but run
as SEPARATE OS processes.

Run the worker with (from backend/, venv activated):
    celery -A app.celery_app worker --loglevel=info

Redis itself must be running first:
    brew services start redis
"""
from celery import Celery

from app.config import settings

celery_app = Celery(
    "kush_medical",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=180,
    task_soft_time_limit=150,
)

import app.services.tasks  # noqa: E402,F401
