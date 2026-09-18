"""
Kush Medical Hall — FastAPI application entry point.

API Versioning:
  All business routers are mounted under the /v1 prefix. In development the
  Vite proxy transparently rewrites /api → /v1, so the frontend always calls
  /api/... and the proxy maps it to /v1/... at the backend.

  The health-check router is intentionally mounted TWICE:
    • /health        — unversioned, for load-balancer / k8s liveness probes
    • /v1/health     — versioned, for programmatic API consumers

  A deprecation shim re-mounts the same routers at their bare paths
  (e.g. /auth/login) so that any tooling or script that used the old
  unversioned URLs continues to work. Those paths are tagged
  "deprecated" in OpenAPI and will be removed in v2.
"""
import traceback

from fastapi import FastAPI, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from app.core.idempotency import IdempotencyMiddleware
from app.core.request_id import RequestIDMiddleware
from app.core.logging import get_logger

_main_logger = get_logger("main")

from app.routers import (
    bills, medicines, dashboard, stock, expiry, analytics, auth, gst,
    health, substitutes, graph, copilot, pos, audit, customers, network,
    symptom_bot, forecast, anomalies, notifications, cold_chain, surveillance, trust_score, smart_purchase, profit,
    prescriptions, register, tenants, setup, network_integrity, regional_health
)
from app.database import ensure_database_schema_synced
from app.events.subscribers import register_all_subscribers
from app.config import settings


# ---------------------------------------------------------------------------
# OpenAPI / FastAPI app definition
# Improved metadata: version tag, contact, license, and per-tag descriptions
# so every section of the Swagger UI has a readable summary.
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Kush Medical Hall — Pharmacy Operating System",
    description=(
        "## Kush Medical Hall API v1\n\n"
        "A full pharmacy operating system covering:\n"
        "- **OCR Bill Digitisation** — upload invoices; AI extracts line items automatically.\n"
        "- **PharmaGraph** — knowledge graph of medicines, salts, conditions, and interactions.\n"
        "- **PharmaCopilot** — Groq-powered AI assistant for clinical/inventory queries.\n"
        "- **Safety Guardrail POS** — drug-interaction checks at checkout.\n"
        "- **TrustChain** — SHA-256 hash-chain audit ledger; tamper-evident.\n"
        "- **Customer Health Companion** — udhaar ledger + adherence tracking.\n"
        "- **Inter-Pharmacy Network** — near-expiry listing exchange.\n"
        "- **Predictive Intelligence** — demand forecast + anomaly detection.\n"
        "- **Notification Engine** — in-app + WhatsApp proactive alerts.\n"
        "- **Cold-Chain Compliance** — temperature monitoring + excursion logging.\n"
        "- **Syndromic Surveillance** — privacy-safe OTC sales trend detection.\n"
        "- **Supply Chain Trust Score** — distributor reliability scoring.\n\n"
        "All endpoints require a Bearer JWT except `/health` and `POST /v1/auth/login`.\n"
        "Obtain tokens via `POST /v1/auth/login` → `{access_token, refresh_token}`.\n"
    ),
    version="3.1.0",
    openapi_url="/api/openapi.json",   # served at /api/openapi.json for Vite proxy compatibility
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    contact={"name": "Kush Medical Hall", "email": "admin@kushmedical.local"},
    license_info={"name": "Private — All Rights Reserved"},
    openapi_tags=[
        {"name": "auth",           "description": "Login, token refresh, logout, user management."},
        {"name": "bills",          "description": "OCR invoice upload, review queue, line-item editing, confirmation."},
        {"name": "medicines",      "description": "Medicine master list — browse, barcode, composition."},
        {"name": "stock",          "description": "Stock snapshots, ledger, reorder list, smart thresholds."},
        {"name": "expiry",         "description": "Expiry tracking dashboard, missing-date filler."},
        {"name": "analytics",      "description": "Financial analytics — monthly spend, top medicines (owner only)."},
        {"name": "gst",            "description": "GST report generation and PDF export (owner only)."},
        {"name": "dashboard",      "description": "High-level summary KPIs for the home screen."},
        {"name": "substitutes",    "description": "Same-salt substitute search and availability check."},
        {"name": "graph",          "description": "PharmaGraph — medicine knowledge graph, interaction checker."},
        {"name": "copilot",        "description": "PharmaCopilot — AI assistant powered by Groq (owner only)."},
        {"name": "pos",            "description": "Point-of-Sale — cart safety check and sale recording."},
        {"name": "audit",          "description": "TrustChain audit ledger — tamper-evidence verification (owner only)."},
        {"name": "customers",      "description": "Customer credit ledger, adherence alerts, outstanding balances."},
        {"name": "network",        "description": "Inter-pharmacy network — listings, claims, fulfilment."},
        {"name": "symptom-bot",    "description": "Symptom-to-stock chatbot — finds in-stock medicines for a symptom."},
        {"name": "forecast",       "description": "Demand forecast — Holt-Winters smoothing per medicine."},
        {"name": "anomalies",      "description": "Price-jump and stock-adjustment anomaly detection."},
        {"name": "notifications",  "description": "Notification centre — in-app alerts, mark-read, digest trigger."},
        {"name": "cold-chain",     "description": "Cold-chain compliance — units, temperature readings, excursion report."},
        {"name": "surveillance",   "description": "Syndromic surveillance — OTC trend conditions, spike detection (owner only)."},
        {"name": "trust-score",    "description": "Supply chain trust scores per distributor (owner only)."},
        {"name": "health",         "description": "System health check — DB, Redis, Celery worker status."},
    ],
)


@app.on_event("startup")
async def on_startup():
    """
    BUG FIX: Run DB schema sync and event subscriber registration on FastAPI
    startup rather than at module import time. This prevents these side-effects
    from running during test collection, module imports in REPL, or hot-reload
    cycles where the DB may not yet be available.
    """
    ensure_database_schema_synced()
    register_all_subscribers()


# ---------------------------------------------------------------------------
# Priority 2a: Rate limiting via slowapi
# Applied only to POST /v1/auth/login — 5 attempts per minute per IP.
# ---------------------------------------------------------------------------
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from app.core.rate_limit import limiter

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

except ImportError:
    import logging
    logging.getLogger("main").warning(
        "slowapi not installed — login rate limiting is disabled. "
        "Install with: pip install slowapi==0.1.9"
    )

# ---------------------------------------------------------------------------
# Priority 2e: Sentry error tracking
# ---------------------------------------------------------------------------
if settings.sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[FastApiIntegration(), CeleryIntegration()],
            traces_sample_rate=0.1,
            environment="production",
        )
    except ImportError:
        import logging
        logging.getLogger("main").warning(
            "sentry-sdk not installed — error tracking disabled. "
            "Install with: pip install sentry-sdk[fastapi]==2.14.0"
        )

# ---------------------------------------------------------------------------
# Priority 2e: Prometheus metrics
# ---------------------------------------------------------------------------
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except ImportError:
    import logging
    logging.getLogger("main").warning(
        "prometheus-fastapi-instrumentator not installed — /metrics endpoint disabled. "
        "Install with: pip install prometheus-fastapi-instrumentator==7.0.0"
    )

# BUG FIX: allow_origins=["*"] is insecure in production — any website could
# send credentialed requests to this API. Since we use JWT in Authorization
# header (not cookies), allow_credentials is not needed. For production,
# set ALLOWED_ORIGINS env var to your frontend's actual domain.
_cors_origins_raw = getattr(settings, "allowed_origins", "")
if _cors_origins_raw:
    _allowed_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
else:
    # Development fallback — Vite dev server and common localhost ports only.
    _allowed_origins = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,  # not needed; we use Authorization header, not cookies
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Requested-With"],
)

# ---------------------------------------------------------------------------
# Priority 4: Idempotency middleware
# Protects POST/PATCH/DELETE from double-execution on client retries.
# Clients send `Idempotency-Key: <uuid4>` header; the middleware caches the
# response in Redis for 24 h and replays it on duplicate requests.
# Starlette processes middlewares in LIFO order, so IdempotencyMiddleware is
# added AFTER CORSMiddleware to run *inside* CORS (correct layering).
# ---------------------------------------------------------------------------
app.add_middleware(IdempotencyMiddleware)

# ---------------------------------------------------------------------------
# Request ID middleware — generates a per-request UUID4 correlation ID.
# Must be added LAST (Starlette LIFO) so it runs OUTERMOST and the ID is
# available on request.state for all downstream handlers, including the
# global exception handlers below.
# ---------------------------------------------------------------------------
app.add_middleware(RequestIDMiddleware)


# ---------------------------------------------------------------------------
# Task 1 — Global exception handlers
#
# IMPORTANT: these run AFTER Sentry's FastAPI integration, which already
# hooks into the ASGI cycle at the middleware level before our handlers.
# So Sentry captures the exception automatically; our handlers just ensure
# the CLIENT response is always sanitised (no raw error details leaked).
# ---------------------------------------------------------------------------

def _get_request_id(request: Request) -> str:
    """Safe accessor for request.state.request_id (set by RequestIDMiddleware)."""
    return getattr(request.state, "request_id", "unknown")


@app.exception_handler(SQLAlchemyError)
async def _sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    """
    Catches any unhandled SQLAlchemy error and returns a generic DB error
    message.  Raw SQL / connection strings are NEVER forwarded to the client.
    """
    request_id = _get_request_id(request)
    _main_logger.error(
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


@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all for any unhandled exception that wasn't caught by a more
    specific handler.  Logs the full traceback server-side and returns a
    sanitised 500 response — no internal detail is ever exposed to the
    client.

    Sentry note: Sentry's FastAPI integration intercepts exceptions at
    the ASGI middleware layer (before our handler sees them), so Sentry
    already captures the event.  This handler does NOT need to call
    sentry_sdk.capture_exception() manually.
    """
    request_id = _get_request_id(request)
    _main_logger.error(
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

# ---------------------------------------------------------------------------
# Routers — versioned (/v1/...) + unversioned legacy (/...) shims
#
# Strategy:
#   1. v1_router — all business routers under /v1 prefix.  This is the
#      canonical, forward-compatible API surface.
#   2. health.router — mounted at / (bare) for load-balancer probes AND
#      as part of v1_router so /v1/health also works.
#   3. Legacy shim — same routers mounted at bare paths for backward
#      compatibility. Tagged "deprecated" in OpenAPI.  Removed in v2.
# ---------------------------------------------------------------------------

# ----- V1 versioned router --------------------------------------------------
v1_router = APIRouter(prefix="/v1")

v1_router.include_router(health.router)        # → /v1/health
v1_router.include_router(auth.router)          # → /v1/auth/...
v1_router.include_router(bills.router)         # → /v1/bills/...
v1_router.include_router(medicines.router)     # → /v1/medicines/...
v1_router.include_router(dashboard.router)     # → /v1/dashboard/...
v1_router.include_router(stock.router)         # → /v1/stock/...
v1_router.include_router(expiry.router)        # → /v1/expiry/...
v1_router.include_router(analytics.router)     # → /v1/analytics/...
v1_router.include_router(gst.router)           # → /v1/gst/...
v1_router.include_router(substitutes.router)   # → /v1/substitutes/...
v1_router.include_router(graph.router)         # → /v1/graph/...
v1_router.include_router(copilot.router)       # → /v1/copilot/...
v1_router.include_router(pos.router)           # → /v1/pos/...
v1_router.include_router(audit.router)         # → /v1/audit/...
v1_router.include_router(customers.router)     # → /v1/customers/...
v1_router.include_router(network.router)       # → /v1/network/...
v1_router.include_router(symptom_bot.router)   # → /v1/symptom-bot/...
v1_router.include_router(forecast.router)      # → /v1/forecast/...
v1_router.include_router(anomalies.router)     # → /v1/anomalies/...
v1_router.include_router(notifications.router) # → /v1/notifications/...
v1_router.include_router(cold_chain.router)    # → /v1/cold-chain/...
v1_router.include_router(surveillance.router)  # → /v1/surveillance/...
v1_router.include_router(trust_score.router)   # → /v1/trust-score/...
v1_router.include_router(smart_purchase.router) # → /v1/smart-purchase/...
v1_router.include_router(profit.router)         # → /v1/profit/...
v1_router.include_router(prescriptions.router) # → /v1/prescriptions/...
v1_router.include_router(setup.router)          # → /v1/setup/... (public setup wizard)
v1_router.include_router(register.router)       # → /v1/register/...
v1_router.include_router(tenants.router)
v1_router.include_router(network_integrity.router)
v1_router.include_router(regional_health.router)  # → /v1/regional-health/...
        # → /v1/tenants/...

app.include_router(v1_router)

# ----- Health at root (for load-balancer probes) ----------------------------
app.include_router(health.router)              # → /health  (no version prefix)

# ----- Legacy shim — bare paths for backward compatibility ------------------
# These were the original unversioned paths. They remain functional so that
# existing scripts/tests/integrations keep working. They will be removed in v2.
_legacy = APIRouter(deprecated=True)
_legacy.include_router(auth.router)
_legacy.include_router(bills.router)
_legacy.include_router(medicines.router)
_legacy.include_router(dashboard.router)
_legacy.include_router(stock.router)
_legacy.include_router(expiry.router)
_legacy.include_router(analytics.router)
_legacy.include_router(gst.router)
_legacy.include_router(substitutes.router)
_legacy.include_router(graph.router)
_legacy.include_router(copilot.router)
_legacy.include_router(pos.router)
_legacy.include_router(audit.router)
_legacy.include_router(customers.router)
_legacy.include_router(network.router)
_legacy.include_router(symptom_bot.router)
_legacy.include_router(forecast.router)
_legacy.include_router(anomalies.router)
_legacy.include_router(notifications.router)
_legacy.include_router(cold_chain.router)
_legacy.include_router(surveillance.router)
_legacy.include_router(trust_score.router)
_legacy.include_router(smart_purchase.router)
_legacy.include_router(profit.router)
_legacy.include_router(prescriptions.router)
_legacy.include_router(network_integrity.router)
_legacy.include_router(regional_health.router)

app.include_router(_legacy)  # bare paths still work — tests pass, scripts work


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------
@app.get("/", tags=["health"])
def root():
    return {
        "status": "ok",
        "service": "kush-medical-backend",
        "architecture": "event-driven-pipeline",
        "api_version": "v1",
        "versioned_base": "/v1",
        "docs": "/api/docs",
        "openapi": "/api/openapi.json",
        "pillars": [
            "PharmaGraph", "PharmaCopilot", "SafetyGuardrail-POS",
            "TrustChain", "CustomerHealthCompanion+Network",
            "PredictiveIntelligence", "NotificationEngine",
        ],
    }
