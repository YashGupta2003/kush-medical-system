"""
Idempotency Middleware for Mutation Safety.

Protects POST, PATCH, and DELETE endpoints from duplicate side-effects caused
by client retries (e.g. timeout → retry → double-sale).

Flow:
  1. Client sends `Idempotency-Key: <uuid4>` header with every mutating request.
  2. On first receipt:  process normally, cache the response body + status code
     in Redis under `idem:<key>` with a 24-hour TTL, then return to client.
  3. On duplicate receipt (same key within 24h): return the cached response
     immediately — no DB write, no business logic executed. Idempotent.
  4. If Redis is unavailable: the middleware is a no-op (fail-open) — the
     request is processed normally.  Better a possible duplicate than an outage.

Key format:  idem:<Idempotency-Key value>
TTL:         86 400 seconds (24 hours)
Scope:       POST, PATCH, DELETE — GET and HEAD are inherently idempotent.

Thread safety: Redis SET NX (set-if-not-exists) is used as a distributed lock
to prevent a race condition where two concurrent retries both see "no cached
response" and both proceed to DB writes simultaneously.  Only one will win the
SETNX; the other will spin-wait briefly and then return the cached response.

The lock key is separate from the response-cache key so that:
  - The lock can have a short TTL (30 s) independent of the 24 h response cache.
  - A failed first-request (e.g. exception before response) releases the lock
    automatically, allowing a genuine retry to proceed.
"""
import json
import time
import sys
import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.cache import get_redis_client
from app.core.logging import get_logger

logger = get_logger("idempotency")

_IDEMPOTENCY_TTL_SECONDS = 86_400   # 24 hours
_LOCK_TTL_SECONDS        = 30       # max time for the first request to finish
_LOCK_POLL_INTERVAL      = 0.05     # 50 ms between lock-poll attempts
_LOCK_MAX_WAIT           = 5.0      # give up waiting after 5 s (fail-open)

# Only POST/PATCH/DELETE carry side-effects; GET/HEAD are already idempotent.
_IDEMPOTENT_METHODS = {"POST", "PATCH", "DELETE"}


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that enforces idempotency for mutating HTTP methods.

    Usage (in main.py):
        from app.core.idempotency import IdempotencyMiddleware
        app.add_middleware(IdempotencyMiddleware)

    Client usage:
        POST /v1/pos/sales
        Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
        Content-Type: application/json
        { ... }
    """

    async def dispatch(self, request: Request, call_next):
        # Only guard mutating methods
        if request.method not in _IDEMPOTENT_METHODS:
            return await call_next(request)

        # In test environments skip Redis entirely — tests run without Redis
        if "pytest" in sys.modules or os.environ.get("TESTING", "").lower() == "true":
            return await call_next(request)

        idem_key = request.headers.get("Idempotency-Key", "").strip()
        if not idem_key:
            # No key provided — pass through normally (backward compatible)
            return await call_next(request)

        # Sanitise the key to prevent Redis key injection
        if len(idem_key) > 128 or not idem_key.replace("-", "").replace("_", "").isalnum():
            return JSONResponse(
                status_code=400,
                content={"detail": "Idempotency-Key must be an alphanumeric string (UUID recommended), max 128 chars."},
            )

        r = get_redis_client()
        if r is None:
            # Redis unavailable — fail-open, process normally
            logger.warning("Idempotency middleware: Redis unavailable, skipping idempotency check.")
            return await call_next(request)

        cache_key = f"idem:{idem_key}"
        lock_key  = f"idem_lock:{idem_key}"

        try:
            # ----------------------------------------------------------------
            # Fast path: response already cached → return immediately
            # ----------------------------------------------------------------
            cached = r.get(cache_key)
            if cached:
                logger.info(f"Idempotency HIT for key '{idem_key}' — returning cached response.")
                payload = json.loads(cached)
                return JSONResponse(
                    status_code=payload["status_code"],
                    content=payload["body"],
                    headers={"X-Idempotency-Replayed": "true"},
                )

            # ----------------------------------------------------------------
            # Acquire a distributed lock so that concurrent retries of the
            # same key don't all race to the DB simultaneously.
            # ----------------------------------------------------------------
            acquired = r.set(lock_key, "1", nx=True, ex=_LOCK_TTL_SECONDS)
            if not acquired:
                # Another request with the same key is in-flight — wait for
                # the response to be cached, then return it.
                waited = 0.0
                while waited < _LOCK_MAX_WAIT:
                    import asyncio
                    await asyncio.sleep(_LOCK_POLL_INTERVAL)
                    waited += _LOCK_POLL_INTERVAL
                    cached = r.get(cache_key)
                    if cached:
                        payload = json.loads(cached)
                        logger.info(f"Idempotency HIT (after lock-wait) for key '{idem_key}'.")
                        return JSONResponse(
                            status_code=payload["status_code"],
                            content=payload["body"],
                            headers={"X-Idempotency-Replayed": "true"},
                        )
                # Lock still held but no cache entry — the first request may
                # have failed.  Fail-open: let this request proceed.
                logger.warning(
                    f"Idempotency lock-wait timed out for key '{idem_key}'. "
                    "Proceeding without idempotency guarantee (fail-open)."
                )
                return await call_next(request)

            # ----------------------------------------------------------------
            # Process the request normally, capture the response body
            # ----------------------------------------------------------------
            try:
                response = await call_next(request)

                # Read and buffer the response body (ASGI streaming)
                body_chunks = []
                async for chunk in response.body_iterator:
                    body_chunks.append(chunk)
                raw_body = b"".join(body_chunks)

                # Only cache successful mutation responses (2xx)
                status_code = response.status_code
                if 200 <= status_code < 300:
                    try:
                        body_json = json.loads(raw_body)
                        cache_payload = json.dumps({"status_code": status_code, "body": body_json})
                        r.setex(cache_key, _IDEMPOTENCY_TTL_SECONDS, cache_payload)
                        logger.info(
                            f"Idempotency STORED for key '{idem_key}' "
                            f"(status={status_code}, TTL={_IDEMPOTENCY_TTL_SECONDS}s)."
                        )
                    except (json.JSONDecodeError, Exception) as e:
                        logger.warning(f"Idempotency: could not cache non-JSON response for key '{idem_key}': {e}")

                # Re-stream the buffered body back to the client
                # BUG FIX: raw_body may be non-JSON (e.g. a PDF blob from GST
                # report download). Fall back to streaming the raw bytes if
                # json.loads fails, preserving the original Content-Type.
                try:
                    body_json = json.loads(raw_body) if raw_body else None
                    return JSONResponse(
                        status_code=status_code,
                        content=body_json,
                        headers={k: v for k, v in response.headers.items() if k.lower() != "content-length"},
                    )
                except (json.JSONDecodeError, ValueError):
                    from starlette.responses import Response as RawResponse
                    return RawResponse(
                        content=raw_body,
                        status_code=status_code,
                        headers={k: v for k, v in response.headers.items() if k.lower() != "content-length"},
                    )

            finally:
                # Always release the lock so that a failed first-request
                # allows a clean retry to proceed.
                try:
                    r.delete(lock_key)
                except Exception:
                    pass

        except Exception as e:
            # Any unexpected Redis error → fail-open
            logger.error(f"Idempotency middleware error (fail-open): {e}", exc_info=True)
            return await call_next(request)
