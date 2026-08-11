"""
Production Health Check Router.
Monitors Database, Redis, and Celery Worker health status.
"""
import time
from typing import Dict, Any
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.config import settings
from app.core.cache import get_redis_client
from app.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger("health")
router = APIRouter(tags=["health"])


@router.get("/health", response_model=Dict[str, Any])
def health_check(response: Response, db: Session = Depends(get_db)):
    """
    Production health check endpoint verifying database, Redis, and Celery worker health.
    """
    health_status: Dict[str, Any] = {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {},
    }
    is_healthy = True

    # 1. Database Health Check
    db_start = time.time()
    try:
        db.execute(text("SELECT 1"))
        db_latency = round((time.time() - db_start) * 1000, 2)
        health_status["services"]["database"] = {
            "status": "up",
            "latency_ms": db_latency,
        }
    except Exception as e:
        is_healthy = False
        logger.error(f"Database health check failed: {e}")
        health_status["services"]["database"] = {
            "status": "down",
            "error": str(e),
        }

    # 2. Redis Cache Health Check
    redis_start = time.time()
    try:
        r = get_redis_client()
        if r and r.ping():
            redis_latency = round((time.time() - redis_start) * 1000, 2)
            health_status["services"]["redis"] = {
                "status": "up",
                "latency_ms": redis_latency,
            }
        else:
            health_status["services"]["redis"] = {
                "status": "degraded",
                "message": "Redis client unreachable or un-pingable",
            }
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        health_status["services"]["redis"] = {
            "status": "degraded",
            "error": str(e),
        }

    # 3. Celery Worker Health Check
    try:
        ping_response = celery_app.control.ping(timeout=0.5)
        active_workers = len(ping_response) if ping_response else 0
        health_status["services"]["celery"] = {
            "status": "up" if active_workers > 0 else "degraded",
            "active_workers": active_workers,
            "details": ping_response,
        }
    except Exception as e:
        logger.warning(f"Celery worker health check failed: {e}")
        health_status["services"]["celery"] = {
            "status": "degraded",
            "error": str(e),
        }

    if not is_healthy:
        health_status["status"] = "unhealthy"
        response.status_code = status.HTTP_533_SERVICE_UNAVAILABLE if hasattr(status, "HTTP_533_SERVICE_UNAVAILABLE") else status.HTTP_503_SERVICE_UNAVAILABLE

    return health_status
