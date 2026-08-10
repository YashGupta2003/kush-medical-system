"""
Celery app instance. The API process (FastAPI/uvicorn) and the worker
process (celery worker) both import this same `celery_app` object, but run
as SEPARATE OS processes.

Run the worker with (from backend/, venv activated):
    celery -A app.celery_app worker --loglevel=info

Run the beat scheduler (for periodic tasks) with:
    celery -A app.celery_app beat --loglevel=info

Redis itself must be running first:
    brew services start redis

Priority 1 beat_schedule additions:
  - run_adherence_check_task: daily at 6am IST — checks for overdue refills
    and fires AdherenceAlertRaisedEvent for new alerts not notified in 7 days
  - run_anomaly_scan_task: daily at 6am IST — runs both anomaly detectors
    and fires AnomalyFlaggedEvent for newly flagged items
  - send_daily_digest_task: daily at 8am IST — builds and delivers the digest
    to all owner accounts
  - publish_near_expiry_listings_task: daily at 7am IST — publishes near-expiry
    batches to the inter-pharmacy network (already existed as a network feature,
    now scheduled)

Priority 2d addition:
  - rebuild_graph_task: weekly (Sunday 2am IST) — the expensive O(catalog)
    full graph rebuild. Daily would be redundant (incremental SUPPLIES sync
    runs on every bill confirm) and wasteful.
"""
from celery import Celery
from celery.schedules import crontab

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

    # ---------------------------------------------------------------------------
    # Celery Beat periodic schedule
    # All times are in IST (Asia/Kolkata) because timezone="Asia/Kolkata" above.
    # ---------------------------------------------------------------------------
    beat_schedule={
        # Priority 2d: Full graph rebuild — weekly (Sunday 2am IST).
        # Daily would be redundant because SUPPLIES edges are incrementally synced
        # on every bill confirm via handle_bill_confirmed_graph_sync. The weekly
        # rebuild is for catching any drift or adding new CONTAINS/TREATS data.
        "rebuild-graph-weekly": {
            "task": "rebuild_graph",
            "schedule": crontab(hour=2, minute=0, day_of_week=0),   # Sunday 2:00am
        },

        # Priority 1: Adherence check — daily at 6am IST.
        # Fires AdherenceAlertRaisedEvent for (customer, medicine) pairs that are
        # overdue and haven't been notified in the last 7 days.
        "run-adherence-check-daily": {
            "task": "run_adherence_check",
            "schedule": crontab(hour=6, minute=0),
        },

        # Priority 1: Anomaly scan — daily at 6:15am IST.
        # Slight offset from adherence check to avoid Redis/DB contention.
        "run-anomaly-scan-daily": {
            "task": "run_anomaly_scan",
            "schedule": crontab(hour=6, minute=15),
        },

        # Priority 1: Daily digest — 8am IST, after all checks have run.
        "send-daily-digest": {
            "task": "send_daily_digest",
            "schedule": crontab(hour=8, minute=0),
        },

        # Priority 1: Near-expiry listings publish — 7am IST.
        # Publishes near-expiry batches to the inter-pharmacy network.
        "publish-near-expiry-daily": {
            "task": "publish_near_expiry_listings",
            "schedule": crontab(hour=7, minute=0),
        },

        # Smart reorder threshold computation — daily at 5am IST.
        # Computes suggested_low_stock_threshold for all medicines using
        # Holt-Winters / flat average from forecast_service.
        "compute-smart-thresholds-daily": {
            "task": "compute_smart_thresholds_bulk",
            "schedule": crontab(hour=5, minute=0),
        },

        # BUG FIX #3: Zombie Bill Cleanup — every 10 minutes.
        # Marks any bill stuck in 'queued' or 'processing' state for more
        # than ZOMBIE_BILL_TIMEOUT_MINUTES (default: 10) as 'failed' so
        # the frontend doesn't show 'Processing...' forever.
        "cleanup-zombie-bills": {
            "task": "cleanup_zombie_bills",
            "schedule": crontab(minute="*/10"),  # every 10 minutes
        },

        # BUG FIX #4: Disk Space Exhaustion — nightly at 3am IST.
        # Deletes uploaded bill image files from disk that are older than
        # UPLOAD_RETENTION_DAYS (default: 90 days). DB rows are preserved;
        # only the disk files are removed to prevent hard-drive exhaustion.
        "cleanup-old-uploads-nightly": {
            "task": "cleanup_old_upload_files",
            "schedule": crontab(hour=3, minute=0),  # 3am IST nightly
        },
    },
)

import app.services.tasks  # noqa: E402,F401
