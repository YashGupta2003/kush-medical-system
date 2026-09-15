"""
Public registration endpoint — no authentication required.

Flow:
  POST /register  →  creates Tenant + owner User  →  returns JWT tokens
  GET  /register/verify?token=<raw_token>  →  marks email verified
  POST /register/lookup  →  given email, returns tenant slug for login redirect

Design decision: we return JWT tokens immediately on registration (before email
verification) so the shop can start the Setup Wizard (medicine import) without
waiting for email. The email_verified flag is a separate UX gate — unverified
accounts are fully functional but a banner reminds them to verify.
"""
from fastapi import APIRouter, Request
from app.core.rate_limit import limiter
from app.config import settings
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app import models
from app.services.tenant_service import create_tenant_with_owner, verify_tenant_email
from app.services.auth_service import create_access_token, create_refresh_token

router = APIRouter(prefix="/register", tags=["registration"])


class ShopRegistrationRequest(BaseModel):
    shop_name: str = Field(..., min_length=2, max_length=150, description="Full name of your pharmacy")
    owner_name: str = Field(..., min_length=2, max_length=100, description="Owner's full name")
    email: str = Field(..., description="Email address — used for login and alerts")
    password: str = Field(..., min_length=8, description="Min 8 characters")
    phone: Optional[str] = Field(None, max_length=20)
    gstin: Optional[str] = Field(None, max_length=20, description="GST registration number (optional)")
    city: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=500)


class RegistrationResponse(BaseModel):
    access_token: str
    refresh_token: str
    role: str
    username: str
    full_name: Optional[str]
    tenant_id: int
    tenant_slug: str
    shop_name: str
    email_verified: bool
    message: str


@router.post("", response_model=RegistrationResponse, summary="Register a new pharmacy")
@limiter.limit(settings.rate_limit_setup)
def register_shop(request: Request, payload: ShopRegistrationRequest, db: Session = Depends(get_db)):
    """
    Register a new pharmacy on the platform.
    Creates a Tenant + Owner User and returns JWT tokens for immediate access.
    A verification email would be sent in production (Twilio/SendGrid).
    """
    tenant, owner, verification_token = create_tenant_with_owner(
        db=db,
        shop_name=payload.shop_name,
        owner_name=payload.owner_name,
        email=payload.email,
        password=payload.password,
        phone=payload.phone,
        gstin=payload.gstin,
        city=payload.city,
        address=payload.address,
    )

    access_token = create_access_token(owner)
    refresh_token = create_refresh_token(db, owner)

    return RegistrationResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        role=owner.role,
        username=owner.username,
        full_name=owner.full_name,
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        shop_name=tenant.shop_name,
        email_verified=tenant.email_verified,
        message=(
            f"Welcome to PharmOS, {tenant.shop_name}! "
            "Your account is ready. Please upload your medicine list to get started."
        )
    )


@router.get("/verify", summary="Verify email address")
def verify_email(token: str, db: Session = Depends(get_db)):
    """
    Called when the shop owner clicks the verification link in their welcome email.
    Marks the tenant's email as verified.
    """
    tenant = verify_tenant_email(db, token)
    return {"message": f"Email verified for {tenant.shop_name}. Thank you!"}


@router.post("/lookup", summary="Look up tenant slug by email or username")
def lookup_tenant(payload: dict, db: Session = Depends(get_db)):
    """
    Given an email or username, returns the tenant slug so the frontend knows which shop
    is logging in. Used by the login form to pre-fill shop context.
    """
    identifier = payload.get("email", "").strip()
    if not identifier:
        raise HTTPException(400, "email or username is required")
        
    # Try by tenant email
    tenant = db.query(models.Tenant).filter(models.Tenant.email == identifier.lower()).first()
    
    # Fallback to checking by username (assuming for now usernames are somewhat unique across tenants, or just picking first)
    if not tenant:
        user = db.query(models.User).filter(models.User.username == identifier).first()
        if user:
            tenant = db.query(models.Tenant).filter(models.Tenant.id == user.tenant_id).first()
            
    if not tenant:
        raise HTTPException(404, "No shop found with this email or username")
    return {"tenant_id": tenant.id, "slug": tenant.slug, "shop_name": tenant.shop_name}
