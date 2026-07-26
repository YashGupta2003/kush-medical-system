from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import bills, medicines, dashboard, stock, expiry, analytics, auth, gst

# Schema is now managed by Alembic migrations (see backend/alembic/).



# from app.database import Base, engine
# from app.routers import bills, medicines, dashboard

# # Creates tables if they don't exist yet. For real schema changes later,
# # switch to Alembic migrations instead of relying on this.
# Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Kush Medical Hall - Bill Digitization & Rate List System",
    description="Uploads pharmacy purchase bills, extracts line items via OCR, "
                "computes true landed cost per unit, and keeps the master rate "
                "list in sync with a full audit trail.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten this to your frontend's actual origin before deploying
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bills.router)
app.include_router(medicines.router)
app.include_router(dashboard.router)
app.include_router(stock.router)
app.include_router(expiry.router)
app.include_router(analytics.router)
app.include_router(auth.router)
app.include_router(gst.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "kush-medical-backend"}
