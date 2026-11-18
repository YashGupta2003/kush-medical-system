"""
Redis caching with an in-memory fallback.

The API never crashes because Redis is unavailable:

* Redis reachable  -> shared distributed cache.
* Redis unreachable -> process-local TTL cache (and uncached execution where
  serialization is impossible).
* Tests             -> Redis is skipped entirely and the decorator executes
  the wrapped function directly, preserving deterministic test behavior.
"""
import functools
import json
import os
import sys
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

import redis

from app.config import settings
from app.core.logging import get_logger

logger = get_logger("cache")

_redis_client: Optional[redis.Redis] = None
_redis_unavailable_until: float = 0.0
_REDIS_RETRY_COOLDOWN_SECONDS = 30.0

# Process-local fallback cache: key -> (expires_at_monotonic, json_payload)
_memory_cache: Dict[str, Tuple[float, str]] = {}
_memory_lock = threading.Lock()


def _is_testing() -> bool:
    return "pytest" in sys.modules or os.environ.get("TESTING", "").lower() == "true"


def _connection_kwargs() -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "socket_timeout": settings.redis_cache_socket_timeout,
        "socket_connect_timeout": settings.redis_socket_connect_timeout,
    }
    if settings.redis_url.startswith("rediss://"):
        kwargs["ssl_cert_reqs"] = settings._ssl_cert_reqs()
    return kwargs


def get_redis_client() -> Optional[redis.Redis]:
    """Return a healthy Redis client, or ``None`` when Redis is unavailable."""
    global _redis_client, _redis_unavailable_until

    if _is_testing():
        return None

    if _redis_client is not None:
        return _redis_client

    now = time.monotonic()
    if now < _redis_unavailable_until:
        return None

    try:
        client = redis.Redis.from_url(settings.redis_url, **_connection_kwargs())
        client.ping()
        _redis_client = client
        _redis_unavailable_until = 0.0
        return client
    except Exception as exc:  # noqa: BLE001 - any transport error means "no cache"
        _redis_client = None
        _redis_unavailable_until = now + _REDIS_RETRY_COOLDOWN_SECONDS
        logger.warning(
            f"Redis cache connection failed: {exc}. "
            "Using in-memory cache fallback for the next 30 seconds."
        )
        return None


def _memory_get(key: str) -> Optional[Any]:
    with _memory_lock:
        entry = _memory_cache.get(key)
        if entry is None:
            return None
        expires_at, payload = entry
        if expires_at <= time.monotonic():
            _memory_cache.pop(key, None)
            return None
        try:
            return json.loads(payload)
        except (TypeError, ValueError):
            _memory_cache.pop(key, None)
            return None


def _memory_set(key: str, value: Any, ttl_seconds: int) -> None:
    try:
        payload = json.dumps(value, default=str)
    except (TypeError, ValueError):
        return
    with _memory_lock:
        _memory_cache[key] = (time.monotonic() + max(ttl_seconds, 1), payload)


def _memory_invalidate(prefix: str) -> int:
    with _memory_lock:
        keys = [key for key in _memory_cache if key.startswith(prefix)]
        for key in keys:
            _memory_cache.pop(key, None)
    return len(keys)


def invalidate_analytics_cache() -> None:
    """Invalidate cached analytics/dashboard/GST entries in Redis and memory."""
    memory_count = _memory_invalidate("kush_cache:")
    if memory_count:
        logger.info(f"Invalidated {memory_count} in-memory cache keys.")

    r = get_redis_client()
    if not r:
        return
    try:
        keys = r.keys("kush_cache:*")
        if keys:
            r.delete(*keys)
            logger.info(f"Invalidated {len(keys)} Redis cache keys under 'kush_cache:*'")
    except Exception as exc:  # noqa: BLE001 - cache invalidation is best-effort
        logger.warning(f"Redis cache invalidation warning: {exc}")


def invalidate_cache_prefix(key_prefix: str) -> None:
    """Remove Redis and in-memory cache entries under one namespaced prefix."""
    prefix = f"{key_prefix.rstrip(':')}:"
    memory_count = _memory_invalidate(prefix)
    redis_count = 0
    r = get_redis_client()
    if r is not None:
        try:
            batch = []
            for key in r.scan_iter(match=f"{prefix}*"):
                batch.append(key)
                if len(batch) >= 500:
                    redis_count += r.delete(*batch)
                    batch.clear()
            if batch:
                redis_count += r.delete(*batch)
        except Exception as exc:  # noqa: BLE001 - cache invalidation is best-effort
            logger.warning(f"Redis cache invalidation warning for '{prefix}*': {exc}")
    if memory_count or redis_count:
        logger.info(
            f"Invalidated clinical cache namespace '{prefix}' "
            f"(memory={memory_count}, redis={redis_count})."
        )


def get_cache_health() -> Dict[str, Any]:
    """Return cache diagnostics without ever raising."""
    if _is_testing():
        return {
            "status": "degraded - using eager fallback",
            "backend": "in-memory",
            "message": "Redis deliberately disabled in test mode",
        }

    r = get_redis_client()
    if not r:
        return {
            "status": "degraded - using eager fallback",
            "backend": "in-memory",
            "message": "Redis unreachable; in-memory cache active",
        }

    try:
        started = time.time()
        r.ping()
        return {
            "status": "healthy",
            "backend": "redis",
            "latency_ms": round((time.time() - started) * 1000, 2),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "offline",
            "backend": "in-memory",
            "error": str(exc),
        }


def cache_response(ttl_seconds: int = 300, key_prefix: str = "kush_cache"):
    """Cache a function result in Redis, with an in-memory fallback."""

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if _is_testing():
                return func(*args, **kwargs)

            clean_args = [
                str(arg) for arg in args
                if not hasattr(arg, "query") and not hasattr(arg, "commit")
            ]
            clean_kwargs = {
                key: str(value) for key, value in kwargs.items()
                if not hasattr(value, "query") and not hasattr(value, "commit")
            }
            cache_key = (
                f"{key_prefix}:{func.__module__}.{func.__name__}:"
                f"{json.dumps(clean_args)}:{json.dumps(clean_kwargs, sort_keys=True)}"
            )

            r = get_redis_client()
            if r is not None:
                try:
                    cached = r.get(cache_key)
                    if cached:
                        logger.debug(f"Redis cache HIT for '{cache_key}'")
                        return json.loads(cached)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"Redis cache read error: {exc}")
                    r = None

            if r is None:
                cached = _memory_get(cache_key)
                if cached is not None:
                    logger.debug(f"Memory cache HIT for '{cache_key}'")
                    return cached

            result = func(*args, **kwargs)

            serializable = result
            if hasattr(serializable, "model_dump"):
                serializable = serializable.model_dump()
            elif hasattr(serializable, "dict"):
                serializable = serializable.dict()

            if serializable is not None:
                if r is not None:
                    try:
                        r.setex(
                            cache_key,
                            ttl_seconds,
                            json.dumps(serializable, default=str),
                        )
                        logger.debug(f"Redis cache SET for '{cache_key}'")
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(f"Redis cache write error: {exc}")
                        _memory_set(cache_key, serializable, ttl_seconds)
                else:
                    _memory_set(cache_key, serializable, ttl_seconds)

            return result

        return wrapper

    return decorator
