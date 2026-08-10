from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import (
    bills, medicines, dashboard, stock, expiry, analytics, auth, gst,
    health, substitutes, graph, copilot, pos, audit, customers, network,
    symptom_bot, forecast, anomalies, notifications, cold_chain, surveillance,
)
from app.database import ensure_database_schema_synced
from app.events.subscribers import register_all_subscribers
from app.config import settings

# Auto-sync DB schema and initialize Event Bus Subscribers on startup
ensure_database_schema_synced()
register_all_subscribers()

app = FastAPI(
    title="Kush Medical Hall - Pharmacy Operating System",
    description=(
        "Full pharmacy operating system: OCR bill digitization, PharmaGraph, "
        "PharmaCopilot, Safety Guardrail POS, TrustChain audit, Customer Health "
        "Companion, Inter-Pharmacy Network, Predictive Intelligence, and "
        "Notification Engine."
    ),
    version="3.0.0",
)

# ---------------------------------------------------------------------------
# Priority 2a: Rate limiting via slowapi
# 5 login attempts per minute per IP — applied only to POST /auth/login
# (not globally, to avoid throttling legitimate high-frequency API calls
# from the frontend like the nav badge unread-count poll).
# ---------------------------------------------------------------------------
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

    limiter = Limiter(key_func=get_remote_address, default_limits=[])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # Apply rate limit specifically to login endpoint
    @app.middleware("http")
    async def rate_limit_login(request: Request, call_next):
        if request.url.path == "/api/auth/login" and request.method == "POST":
            try:
                await limiter._check_request_limit(request, "5/minute")
            except RateLimitExceeded:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many login attempts. Please wait 1 minute before trying again."},
                    headers={"Retry-After": "60"},
                )
        return await call_next(request)

except ImportError:
    # slowapi not installed — log warning, don't crash. Rate limiting is
    # a hardening feature, not a core correctness requirement.
    import logging
    logging.getLogger("main").warning(
        "slowapi not installed — login rate limiting is disabled. "
        "Install with: pip install slowapi==0.1.9"
    )

# ---------------------------------------------------------------------------
# Priority 2e: Sentry error tracking
# Empty-string-safe no-op — exact same pattern as Groq/Twilio.
# ---------------------------------------------------------------------------
if settings.sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[FastApiIntegration(), CeleryIntegration()],
            traces_sample_rate=0.1,      # 10% of requests traced
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(bills.router)
app.include_router(medicines.router)
app.include_router(dashboard.router)
app.include_router(stock.router)
app.include_router(expiry.router)
app.include_router(analytics.router)
app.include_router(auth.router)
app.include_router(gst.router)
app.include_router(substitutes.router)
app.include_router(graph.router)
app.include_router(copilot.router)
app.include_router(pos.router)
app.include_router(audit.router)
app.include_router(customers.router)
app.include_router(network.router)
app.include_router(symptom_bot.router)
app.include_router(forecast.router)
app.include_router(anomalies.router)
# Priority 1: Notification Engine
app.include_router(notifications.router)
app.include_router(cold_chain.router)
app.include_router(surveillance.router)



@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "kush-medical-backend",
        "architecture": "event-driven-pipeline",
        "version": "3.0.0",
        "pillars": [
            "PharmaGraph", "PharmaCopilot", "SafetyGuardrail-POS",
            "TrustChain", "CustomerHealthCompanion+Network",
            "PredictiveIntelligence", "NotificationEngine",
        ],
    }
