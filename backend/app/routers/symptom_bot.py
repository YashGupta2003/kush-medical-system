"""
Symptom-to-Stock Bot endpoint (Pillar 5, Part A.3). See
app/services/symptom_bot_service.py's module docstring for the full
design/safety-boundary rationale and the honest note on what would change
to wire this to a real Twilio WhatsApp webhook.
"""
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter
from app.config import settings
from app.database import get_db
from app import schemas
from app.services import symptom_bot_service
from app.deps import get_current_user

router = APIRouter(prefix="/symptom-bot", dependencies=[Depends(get_current_user)], tags=["symptom-bot"])


@router.post("/query", response_model=schemas.SymptomQueryResponse)
@limiter.limit(settings.rate_limit_copilot)
def query(request: Request, payload: schemas.SymptomQueryRequest, db: Session = Depends(get_db)):
    return symptom_bot_service.answer_symptom_query(db, payload.message)