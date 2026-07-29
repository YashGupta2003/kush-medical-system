"""
Redis Caching & Invalidation Layer.
Provides high-performance caching for heavy analytics, GST reports, and dashboard stats,
with automatic event-driven cache invalidation.
"""
import os
import sys
import json
import functools
from typing import Any, Callable, Optional
import redis

from app.config import settings
from app.core.logging import get_logger

logger = get_logger("cache")

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """Returns a connected Redis client, or None if unavailable."""
    global _redis_client
    if "pytest" in sys.modules or os.environ.get("TESTING") == "true":
        return None

    if _redis_client is not None:
        return _redis_client
    try:
        client = redis.Redis.from_url(settings.redis_url, socket_timeout=1.0)
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis cache connection failed: {e}. Falling back to un-cached execution.")
        return None


def invalidate_analytics_cache() -> None:
    """Invalidates all cached analytics, dashboard stats, and GST report entries."""
    r = get_redis_client()
    if not r:
        return
    try:
        keys = r.keys("kush_cache:*")
        if keys:
            r.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cache keys under 'kush_cache:*'")
    except Exception as e:
        logger.warning(f"Cache invalidation warning: {e}")


def cache_response(ttl_seconds: int = 300, key_prefix: str = "kush_cache"):
    """
    Decorator for caching service function results in Redis.
    Serializes output to JSON. If Redis is unavailable or in test environment,
    runs target function directly.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if "pytest" in sys.modules or os.environ.get("TESTING") == "true":
                return func(*args, **kwargs)

            r = get_redis_client()
            if not r:
                return func(*args, **kwargs)

            clean_args = [str(arg) for arg in args if not hasattr(arg, "query") and not hasattr(arg, "commit")]
            clean_kwargs = {k: str(v) for k, v in kwargs.items() if not hasattr(v, "query") and not hasattr(v, "commit")}
            cache_key = f"{key_prefix}:{func.__name__}:{json.dumps(clean_args)}:{json.dumps(clean_kwargs, sort_keys=True)}"

            try:
                cached_data = r.get(cache_key)
                if cached_data:
                    logger.debug(f"Cache HIT for key '{cache_key}'")
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Cache read error: {e}")

            result = func(*args, **kwargs)

            try:
                if result is not None:
                    serializable_result = result
                    if hasattr(result, "model_dump"):
                        serializable_result = result.model_dump()
                    elif hasattr(result, "dict"):
                        serializable_result = result.dict()
                    r.setex(cache_key, ttl_seconds, json.dumps(serializable_result, default=str))
                    logger.debug(f"Cache SET for key '{cache_key}' (TTL={ttl_seconds}s)")
            except Exception as e:
                logger.warning(f"Cache write error: {e}")

            return result
        return wrapper
    return decorator
