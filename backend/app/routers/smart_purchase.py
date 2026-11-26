from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any

from app.database import get_db
from app.schemas import SmartPurchaseOrder, SmartPurchaseItem, WhatsAppOrderRequest, WhatsAppOrderResponse
from app.services.smart_purchase_service import generate_purchase_order
from app.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/smart-purchase", tags=["smart-purchase"])

@router.get("/order", response_model=SmartPurchaseOrder)
def get_smart_purchase_order(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate purchase order (owner only)"""
    if current_user.role != 'owner':
        raise HTTPException(status_code=403, detail="Not authorized")
        
    result = generate_purchase_order(db)
    return result

@router.get("/order/{medicine_id}", response_model=SmartPurchaseItem)
def get_single_medicine_purchase_detail(
    medicine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Single medicine detail (owner only)"""
    if current_user.role != 'owner':
        raise HTTPException(status_code=403, detail="Not authorized")
        
    result = generate_purchase_order(db)
    for group in result.get("groups", []):
        for item in group.get("items", []):
            if item["medicine_id"] == medicine_id:
                return item
                
    raise HTTPException(status_code=404, detail="Medicine not found in purchase order")

@router.post("/send-whatsapp", response_model=WhatsAppOrderResponse)
def send_whatsapp_order(
    request: WhatsAppOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send order to distributor via WhatsApp"""
    if current_user.role != 'owner':
        raise HTTPException(status_code=403, detail="Not authorized")
        
    from app.services import whatsapp_service
    
    # Format the message
    lines = [f"Order for {request.distributor_name}:"]
    for item in request.items:
        unit_str = f" {item.unit}" if item.unit else ""
        lines.append(f"- {item.medicine_name}: {item.order_qty}{unit_str}")
        
    message = "\n".join(lines)
    
    # Try sending
    try:
        sent = whatsapp_service.send_message(request.phone, message)
        if not sent:
            return WhatsAppOrderResponse(
                status="failed",
                error="WhatsApp delivery failed or Twilio is not configured.",
            )
        return WhatsAppOrderResponse(status="success", message_id="whatsapp_sent")
    except Exception as e:
        return WhatsAppOrderResponse(status="failed", error=str(e))
