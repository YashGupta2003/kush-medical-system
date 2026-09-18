from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Request, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

from app.core.rate_limit import limiter
from app.config import settings
from app.database import get_db
from app.deps import get_current_tenant, get_current_user
from app.core.upload_validation import validate_audio_upload
from app.services import voice_command_service, stock_service
from app import models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

class VoiceConfirmRequest(BaseModel):
    intent: str
    medicine_id: int
    quantity: int

@router.post("/command")
@limiter.limit(settings.rate_limit_voice)
def handle_voice_command(
    request: Request,
    audio_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant: models.Tenant = Depends(get_current_tenant),
    current_user: models.User = Depends(get_current_user),
):
    try:
        audio_bytes, mime_type = validate_audio_upload(audio_file)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid audio file upload.")

    try:
        parsed_result = voice_command_service.parse_voice_command(audio_bytes, mime_type)
    except Exception as e:
        logger.error(f"Gemini API parsing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Voice assistant is temporarily unavailable, please enter manually"
        )
    
    resolved = voice_command_service.resolve_medicine_intent(db, tenant.id, parsed_result)
    
    return resolved


@router.post("/confirm")
def handle_voice_confirm(
    req: VoiceConfirmRequest,
    db: Session = Depends(get_db),
    tenant: models.Tenant = Depends(get_current_tenant),
    current_user: models.User = Depends(get_current_user),
):
    medicine = db.get(models.Medicine, req.medicine_id)
    if not medicine or medicine.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Medicine not found")

    if req.intent == "sell":
        result = stock_service.record_sale(
            db=db,
            tenant_id=tenant.id,
            medicine_id=req.medicine_id,
            qty_sold=float(req.quantity),
            created_by_user_id=current_user.id
        )
        db.commit()
        return {"status": "success", "message": "Sale recorded successfully", "details": result}

    elif req.intent == "restock":
        current_stock = float(medicine.current_stock) if medicine.current_stock else 0.0
        new_total_stock = current_stock + float(req.quantity)
        result = stock_service.record_adjustment(
            db=db,
            medicine_id=req.medicine_id,
            new_total_stock=new_total_stock,
            note="Voice command restock",
            created_by_user_id=current_user.id
        )
        db.commit()
        return {"status": "success", "message": "Restock recorded successfully", "details": result}

    elif req.intent == "check_stock":
        result = stock_service.get_stock_snapshot(db, tenant.id, req.medicine_id)
        return {"status": "success", "message": "Stock snapshot retrieved", "details": result}
    
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported intent: {req.intent}")
