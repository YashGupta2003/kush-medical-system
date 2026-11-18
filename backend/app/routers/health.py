"""
Production health checks.

Three endpoints with deliberately different semantics:

* ``/health/live``  — process liveness. Always 200; never touches Redis/Celery.
* ``/health/ready`` — traffic readiness. 200 when the database is reachable;
  Redis/Celery fallback mode is *not* a readiness failure.
* ``/health``       — full diagnostic report. Degraded infrastructure returns
  200 with an explicit status string so container liveness is never failed by
  an optional broker. Only a database outage produces 503.
"""
import time
from typing import Any, Dict, Tuple

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.cache import get_cache_health
from app.core.logging import get_logger
from app.core.task_dispatch import runtime_mode
from app.database import get_db

logger = get_logger("health")
router = APIRouter(tags=["health"])

_HEALTHY = "healthy"
_DEGRADED = "degraded - using eager fallback"
_OFFLINE = "offline"


def _check_database(db: Session) -> Dict[str, Any]:
    started = time.time()
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": _HEALTHY,
            "latency_ms": round((time.time() - started) * 1000, 2),
        }
    except Exception as exc:  # noqa: BLE001 - reported, never raised
        logger.error(f"Database health check failed: {exc}")
        return {"status": _OFFLINE, "error": str(exc)}


def _check_celery() -> Dict[str, Any]:
    # Never open a broker socket during tests — the whole suite runs without
    # Redis/Celery and must stay deterministic.
    if settings.is_testing:
        return {
            "status": _DEGRADED,
            "active_workers": 0,
            "message": "Broker checks disabled in test environment",
        }

    if runtime_mode() == "eager_fallback":
        return {
            "status": _DEGRADED,
            "active_workers": 0,
            "message": "CELERY_TASK_ALWAYS_EAGER enabled or sync fallback active",
        }

    try:
        from app.celery_app import celery_app

        ping_response = celery_app.control.ping(timeout=0.5)
        active_workers = len(ping_response) if ping_response else 0
        if active_workers:
            return {"status": _HEALTHY, "active_workers": active_workers}
        if settings.use_sync_tasks_fallback:
            return {
                "status": _DEGRADED,
                "active_workers": 0,
                "message": "No Celery workers detected; dispatcher will fall back inline",
            }
        return {"status": _OFFLINE, "active_workers": 0}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Celery worker health check failed: {exc}")
        if settings.use_sync_tasks_fallback:
            return {"status": _DEGRADED, "error": str(exc)}
        return {"status": _OFFLINE, "error": str(exc)}


def _normalise_cache(cache: Dict[str, Any]) -> Dict[str, Any]:
    """Map cache diagnostics onto the documented health vocabulary."""
    result = dict(cache)
    if result.get("status") == _HEALTHY:
        return result
    if settings.use_sync_tasks_fallback:
        result["status"] = _DEGRADED
    else:
        result["status"] = _OFFLINE
    return result


@router.get("/health/live", response_model=Dict[str, Any])
def live_health() -> Dict[str, Any]:
    """Kubernetes/Render liveness probe: process is up, nothing external."""
    return {
        "status": _HEALTHY,
        "mode": runtime_mode(),
        "timestamp": time.time(),
    }


@router.get("/health/ready", response_model=Dict[str, Any])
def ready_health(response: Response, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Readiness probe: only the mandatory database can fail readiness."""
    database = _check_database(db)
    if database["status"] != _HEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": _HEALTHY if database["status"] == _HEALTHY else _OFFLINE,
        "mode": runtime_mode(),
        "timestamp": time.time(),
        "services": {"database": database},
    }


@router.get("/health", response_model=Dict[str, Any])
def health_check(response: Response, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Full dependency report. Degraded Redis/Celery never fail this endpoint."""
    database = _check_database(db)
    cache = _normalise_cache(get_cache_health())
    celery = _check_celery()

    services = {
        "database": database,
        "redis": cache,
        "celery": celery,
    }

    if database["status"] != _HEALTHY:
        overall = _OFFLINE
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif any(service["status"] != _HEALTHY for service in services.values()):
        overall = _DEGRADED
    else:
        overall = _HEALTHY

    return {
        "status": overall,
        "mode": runtime_mode(),
        "timestamp": time.time(),
        "services": services,
    }
