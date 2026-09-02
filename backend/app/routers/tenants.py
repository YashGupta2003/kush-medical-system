"""
Tenant management — get current shop info, update settings.
All endpoints require authentication (owner-only for mutations).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app import models
from app.deps import get_current_user, require_owner, get_current_tenant

router = APIRouter(prefix="/tenant", tags=["tenant"])


class TenantOut(BaseModel):
    id: int
    slug: str
    shop_name: str
    owner_name: Optional[str]
    email: str
    phone: Optional[str]
    gstin: Optional[str]
    city: Optional[str]
    address: Optional[str]
    plan: str
    email_verified: bool
    is_active: bool

    class Config:
        from_attributes = True


class TenantUpdateRequest(BaseModel):
    shop_name: Optional[str] = None
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    gstin: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    whatsapp_number: Optional[str] = None


@router.get("", response_model=TenantOut, summary="Get current shop info")
def get_tenant(
    tenant: models.Tenant = Depends(get_current_tenant),
):
    """Returns the current shop's profile information."""
    return tenant


@router.patch("", response_model=TenantOut, summary="Update shop settings")
def update_tenant(
    payload: TenantUpdateRequest,
    tenant: models.Tenant = Depends(get_current_tenant),
    current_user: models.User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """Owner-only: update shop name, contact details, GST number."""
    if payload.shop_name is not None:
        tenant.shop_name = payload.shop_name
    if payload.owner_name is not None:
        tenant.owner_name = payload.owner_name
    if payload.phone is not None:
        tenant.phone = payload.phone
    if payload.gstin is not None:
        tenant.gstin = payload.gstin
    if payload.city is not None:
        tenant.city = payload.city
    if payload.address is not None:
        tenant.address = payload.address
    db.commit()
    db.refresh(tenant)
    return tenant
