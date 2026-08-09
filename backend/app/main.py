from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import bills, medicines, dashboard, stock, expiry, analytics, auth, gst, health, substitutes, graph, copilot, pos, audit, customers, network, symptom_bot,forecast, anomalies
from app.database import ensure_database_schema_synced
from app.events.subscribers import register_all_subscribers

# Auto-sync DB schema and initialize Event Bus Subscribers on startup
ensure_database_schema_synced()
register_all_subscribers()

app = FastAPI(
    title="Kush Medical Hall - Bill Digitization & Rate List System",
    description="Uploads pharmacy purchase bills, extracts line items via OCR, "
                "computes true landed cost per unit, and keeps the master rate "
                "list in sync with a full audit trail.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/")
def root():
    return {"status": "ok", "service": "kush-medical-backend", "architecture": "event-driven-pipeline"}
