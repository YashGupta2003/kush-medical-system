"""
Tests for Task 1: global exception handler, SQLAlchemy error handler, and
per-request X-Request-ID middleware.
"""
import pytest
import logging
from fastapi import APIRouter


# ---------------------------------------------------------------------------
# Helper: register a test-only route via add_api_route (FastAPI-native so
# exception handlers work correctly through the routing layer).
# ---------------------------------------------------------------------------

def _inject_api_route(app, path, exc_factory):
    """
    Adds a temporary GET API route that raises the exception produced by
    exc_factory(). Returns a cleanup function.
    """
    route_added = False

    async def raiser():
        raise exc_factory()

    app.add_api_route(path, raiser, methods=["GET"], include_in_schema=False)
    # rebuild router so the route is active
    app.openapi_schema = None

    # Remove by finding the route in app.routes
    added_route = None
    for r in app.routes:
        if hasattr(r, "path") and r.path == path:
            added_route = r

    def cleanup():
        if added_route and added_route in app.routes:
            app.routes.remove(added_route)
        app.openapi_schema = None

    return cleanup


# ---------------------------------------------------------------------------
# Test 1a: generic unhandled exception → 500, no traceback in body, has
# request_id, and X-Request-ID header is present.
# ---------------------------------------------------------------------------

def test_global_exception_handler_returns_500(client, caplog):
    """An endpoint that raises RuntimeError should return 500 with a sanitised body."""
    from app.main import app

    cleanup = _inject_api_route(app, "/test-boom-runtime", lambda: RuntimeError("secret internal detail"))
    try:
        with caplog.at_level(logging.ERROR, logger="main"):
            resp = client.get("/test-boom-runtime")
    finally:
        cleanup()

    assert resp.status_code == 500
    body = resp.json()

    # Sanitised message — no internal detail
    assert body["detail"] == "Internal server error"
    assert "secret internal detail" not in resp.text
    assert "Traceback" not in resp.text
    assert "RuntimeError" not in resp.text

    # request_id is present and non-empty
    assert "request_id" in body
    assert body["request_id"]

    # X-Request-ID response header is set
    header_keys_lower = {k.lower() for k in resp.headers.keys()}
    assert "x-request-id" in header_keys_lower


def test_global_exception_handler_logs_real_exception(client, caplog):
    """The real exception message must appear in the server-side log."""
    from app.main import app
    import logging as _logging

    cleanup = _inject_api_route(app, "/test-boom-log", lambda: RuntimeError("logged-secret-detail-xyz"))
    try:
        # Use the root logger level to capture all loggers since get_logger()
        # sets propagate=False which prevents caplog from intercepting individual
        # named loggers. We also add a handler directly to the "main" logger.
        main_logger = _logging.getLogger("main")
        original_propagate = main_logger.propagate
        main_logger.propagate = True
        try:
            with caplog.at_level(_logging.ERROR):
                client.get("/test-boom-log")
        finally:
            main_logger.propagate = original_propagate
    finally:
        cleanup()

    all_messages = " ".join(r.getMessage() for r in caplog.records)
    assert "logged-secret-detail-xyz" in all_messages


# ---------------------------------------------------------------------------
# Test 1b: SQLAlchemy error → 500, DB-specific sanitised message.
# ---------------------------------------------------------------------------

def test_sqlalchemy_exception_handler_returns_500(client):
    """An endpoint that raises OperationalError should return 500 with a DB message."""
    from app.main import app
    from sqlalchemy.exc import OperationalError

    def make_db_exc():
        return OperationalError("SELECT 1", {}, Exception("connection refused"))

    cleanup = _inject_api_route(app, "/test-dberror-op", make_db_exc)
    try:
        resp = client.get("/test-dberror-op")
    finally:
        cleanup()

    assert resp.status_code == 500
    body = resp.json()

    # Generic DB message, not raw SQL
    assert "database error" in body["detail"].lower()
    assert "SELECT 1" not in resp.text
    assert "connection refused" not in resp.text

    # request_id present
    assert "request_id" in body
    assert body["request_id"]


# ---------------------------------------------------------------------------
# Test 1c: X-Request-ID middleware on a normal (non-error) request
# ---------------------------------------------------------------------------

def test_request_id_header_on_success(client):
    """Every response should carry an X-Request-ID header."""
    resp = client.get("/health")
    assert resp.status_code == 200
    header_keys_lower = {k.lower() for k in resp.headers.keys()}
    assert "x-request-id" in header_keys_lower
    rid = resp.headers.get("x-request-id") or resp.headers.get("X-Request-ID")
    assert rid  # non-empty


def test_request_id_echoes_client_supplied_value(client):
    """If the client sends X-Request-ID we should echo it back unchanged."""
    custom_id = "my-trace-id-12345"
    resp = client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp.status_code == 200
    echoed = resp.headers.get("x-request-id") or resp.headers.get("X-Request-ID")
    assert echoed == custom_id
