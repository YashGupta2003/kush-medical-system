"""
Request ID Middleware.

Generates a per-request UUID4 correlation ID, attaches it to
`request.state.request_id`, and echoes it back as an `X-Request-ID`
response header so errors logged server-side can be grepped by the
client-visible ID.

If the client sends an `X-Request-ID` header, we honour it (useful
for end-to-end tracing from a reverse proxy); otherwise we generate a
fresh UUID4.

This is deliberately a thin, no-dependency middleware so it runs as
early as possible in the stack (added to main.py after CORS but before
all business logic).

NOTE on BaseHTTPMiddleware + exception handlers:
  Starlette's BaseHTTPMiddleware re-raises exceptions from call_next(),
  which means app-level exception handlers registered via
  @app.exception_handler() are bypassed for unhandled exceptions that
  bubble through any BaseHTTPMiddleware layer.
  
  To work around this, this middleware (which is added last / runs
  outermost) also acts as the catch-all error handler for generic
  unhandled exceptions and SQLAlchemy errors. It delegates to the same
  handler functions defined in main.py through a module-level registry
  that main.py populates after defining the handlers.
"""
import traceback
import uuid
import logging

from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("main")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Attach a UUID4 correlation ID to every request/response pair AND
    act as the outermost exception handler for unhandled errors that
    bubble through inner BaseHTTPMiddleware layers.
    """

    async def dispatch(self, request: Request, call_next):
        # Honour a forwarded ID from a reverse-proxy / upstream service;
        # generate a fresh one if absent.
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        except SQLAlchemyError as exc:
            logger.error(
                "SQLAlchemyError on %s %s [request_id=%s]: %s\n%s",
                request.method, request.url.path, request_id,
                exc, traceback.format_exc()
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "A database error occurred. Please try again later.",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )
        except Exception as exc:
            # Log with full traceback; NEVER forward internal details to client.
            logger.error(
                "Unhandled exception on %s %s [request_id=%s]: %r\n%s",
                request.method, request.url.path, request_id,
                exc, traceback.format_exc()
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )
