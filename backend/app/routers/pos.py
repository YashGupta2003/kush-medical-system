"""
Point-of-sale endpoints (Pillar 3) - the safety-checked cart flow for
recording a sale of multiple medicines together. Kept in its own router,
separate from routers/stock.py's existing single-item /stock/sales
endpoint, so this addition never risks touching that file's existing
behavior.

Pillar 5: CartSaleRequest optionally carries customer_id and payment_mode
("cash" | "credit"), passed through to pos_service.record_cart_sale.

Pillar 6: the logged-in staff member's id is captured here and passed as
created_by_user_id, so cart sales - like manual stock adjustments - are
attributable to a staff account for anomaly_service.py's per-staff
analysis.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.services import pos_service
from app.deps import get_current_user

router = APIRouter(prefix="/pos", tags=["pos"], dependencies=[Depends(get_current_user)])


@router.post("/check-cart", response_model=schemas.CartSaleResponse)
def check_cart(payload: schemas.CartSaleRequest, db: Session = Depends(get_db)):
    """
    Dry-run: checks a cart for interactions WITHOUT recording anything -
    powers live, as-you-add-items warnings in the Point of Sale UI.
    """
    check = pos_service.check_cart_interactions(db, [i.model_dump() for i in payload.items])
    return {"status": "checked", "results": [], **check}


@router.post("/sales", response_model=schemas.CartSaleResponse)
def record_cart_sale(
    payload: schemas.CartSaleRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Records every item in the cart. Blocked with status="needs_confirmation"
    (nothing recorded) if an interaction is found and confirm_override
    wasn't set - resend the same request with confirm_override=true once
    the pharmacist has explicitly acknowledged the warning.
    """
    result = pos_service.record_cart_sale(
        db, [i.model_dump() for i in payload.items], confirm_override=payload.confirm_override,
        customer_id=payload.customer_id, payment_mode=payload.payment_mode,
        created_by_user_id=current_user.id,
    )
    return result