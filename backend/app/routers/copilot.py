"""
PharmaCopilot endpoint - owner/staff-facing chat over the shop's own data.
Kept owner-only for now (see router dependency below) since several tools
expose financial data (GST, spend, margins) that this codebase already
treats as owner-only elsewhere (see routers/analytics.py, routers/gst.py).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.services import copilot_service
from app.deps import require_owner

router = APIRouter(prefix="/copilot", dependencies=[Depends(require_owner)], tags=["copilot"])


@router.post("/chat", response_model=schemas.CopilotChatResponse)
def chat(payload: schemas.CopilotChatRequest, db: Session = Depends(get_db)):
    """
    One turn of the PharmaCopilot conversation. Pass back whatever
    `history` the previous response returned to continue the same
    conversation - the frontend treats it as an opaque blob, it doesn't
    need to understand its structure.
    """
    result = copilot_service.run_copilot_query(db, payload.message, history=payload.history)
    return result