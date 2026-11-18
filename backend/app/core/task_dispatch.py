"""
Unified Celery dispatcher with production-safe fallback.

Every enqueue in the application goes through :func:`dispatch_task`. This gives
one auditable place to implement the two supported runtime modes:

* **Broker mode** — enqueue to Redis/Celery. If the broker raises a connection
  error, fall back automatically (inline or via FastAPI ``BackgroundTasks``).
* **Eager mode** — execute the task function in-process. No Redis, no worker,
  no Beat process required (ideal for free-tier/minor-project deployments).

The helper never raises a broker connection error to an HTTP handler when
``USE_SYNC_TASKS_FALLBACK=true``, which is what previously turned a Redis blip
into a 500 after a bill had already been committed.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import BackgroundTasks
from kombu.exceptions import KombuError, OperationalError as KombuOperationalError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError, TimeoutError as RedisTimeoutError

from app.config import settings
from app.core.logging import get_logger

logger = get_logger("task_dispatch")

# Broker/transport failures that must never become a user-facing 500.
_BROKER_ERRORS = (
    KombuOperationalError,
    KombuError,
    RedisConnectionError,
    RedisTimeoutError,
    RedisError,
    ConnectionError,
    OSError,
)

# Results of eager/background fallback executions, keyed by synthetic task id.
# This lets GET /graph/rebuild/{task_id}/status work without a result backend.
_inline_results: Dict[str, Any] = {}


@dataclass(frozen=True)
class TaskDispatchResult:
    """Stable return shape for every dispatcher call."""

    task_id: str
    mode: str                 # broker | eager | background | test
    executed: bool
    result: Any = None
    error: Optional[str] = None


def _in_test_environment() -> bool:
    """Kept as a function so tests can patch it without touching settings."""
    return settings.is_testing


def _task_name(task: Any) -> str:
    return getattr(task, "name", None) or getattr(task, "__name__", "task")


def _synthetic_task_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _normalise_result(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        return result
    if result is None:
        return {"status": "ok"}
    return {"status": "ok", "result": result}


def _run_inline_task(task: Any, args: tuple, kwargs: dict) -> Dict[str, Any]:
    """Execute the underlying task function without a worker process."""
    try:
        run = getattr(task, "run", task)
        return _normalise_result(run(*args, **kwargs))
    except Exception as exc:  # noqa: BLE001 - task failures are data, not HTTP errors
        logger.error(
            f"Inline task '{_task_name(task)}' failed: {exc}", exc_info=True
        )
        return {"status": "failed", "error": str(exc)}


def dispatch_task(
    task: Any,
    *args: Any,
    background_tasks: Optional[BackgroundTasks] = None,
    **kwargs: Any,
) -> TaskDispatchResult:
    """Dispatch ``task`` safely and always return a usable task id.

    Args:
        task: Celery task object (never a string task name).
        *args: Positional task arguments.
        background_tasks: FastAPI ``BackgroundTasks`` for non-blocking fallback.
        **kwargs: Keyword task arguments.

    Returns:
        TaskDispatchResult with ``task_id``, ``mode`` and immediate ``result``
        when the task ran inline.
    """
    task_name = _task_name(task)

    # Test seam: preserve the historical async contract without requiring a
    # live Redis container or accidentally running OCR/anomaly jobs in tests.
    if _in_test_environment():
        return TaskDispatchResult(
            task_id=_synthetic_task_id("test"), mode="test", executed=False
        )

    # Mode A — explicit eager execution.
    if settings.celery_task_always_eager:
        task_id = _synthetic_task_id("eager")
        result = _run_inline_task(task, args, kwargs)
        _inline_results[task_id] = result
        logger.info(f"Task '{task_name}' executed eagerly ({task_id}).")
        return TaskDispatchResult(task_id, "eager", True, result)

    # Mode B — enqueue to the managed broker.
    try:
        async_result = task.apply_async(args=list(args), kwargs=kwargs)
        return TaskDispatchResult(
            task_id=str(async_result.id), mode="broker", executed=False
        )
    except _BROKER_ERRORS as exc:
        if not settings.use_sync_tasks_fallback:
            logger.error(
                f"Broker dispatch failed for '{task_name}' and sync fallback is "
                f"disabled: {exc}"
            )
            raise

        logger.warning(
            f"Redis/Celery broker unavailable for '{task_name}': {exc}. "
            "Using synchronous fallback so the request still succeeds."
        )
        task_id = _synthetic_task_id("eager")

        if background_tasks is not None:
            def _store_background_result() -> None:
                result = _run_inline_task(task, args, kwargs)
                _inline_results[task_id] = result

            background_tasks.add_task(_store_background_result)
            return TaskDispatchResult(
                task_id, "background", False, error=str(exc)
            )

        result = _run_inline_task(task, args, kwargs)
        _inline_results[task_id] = result
        return TaskDispatchResult(task_id, "eager", True, result, str(exc))


def get_task_status(task_id: str) -> Dict[str, Any]:
    """Return a sanitized status dict without requiring a live result backend."""
    if task_id.startswith(("eager-", "test-")):
        result = _inline_results.get(task_id)
        if result is None:
            return {"status": "pending", "mode": "eager"}
        payload = dict(result)
        payload.setdefault("status", "ok")
        payload["mode"] = "eager"
        return payload

    try:
        from app.celery_app import celery_app  # lazy avoids import cycles

        result = celery_app.AsyncResult(task_id)
        state = result.state
        if state == "PENDING":
            return {"status": "pending", "mode": "broker"}
        if state == "SUCCESS":
            payload = _normalise_result(result.result)
            payload["mode"] = "broker"
            return payload
        if state == "FAILURE":
            return {
                "status": "failed",
                "error": str(result.info),
                "mode": "broker",
            }
        return {"status": state.lower(), "mode": "broker"}
    except _BROKER_ERRORS as exc:
        logger.warning(f"Could not read Celery result for {task_id}: {exc}")
        return {
            "status": "degraded - using eager fallback",
            "error": str(exc),
            "mode": "eager",
        }


def runtime_mode() -> str:
    """Single source of truth for health/deployment reporting."""
    if settings.celery_task_always_eager:
        return "eager_fallback"
    return "broker_with_sync_fallback" if settings.use_sync_tasks_fallback else "broker_only"
