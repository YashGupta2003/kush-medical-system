from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.deps import get_current_user, require_owner
from app.services.auth_service import (
    authenticate_user, create_access_token, hash_password,
    create_refresh_token, verify_refresh_token, revoke_refresh_token,
    revoke_all_tokens_for_user,
)

from app.core.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=schemas.TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    """
    Priority 2a: Rate limited to 5 requests/minute/IP via slowapi.
    Returns both access_token (12h) and refresh_token (30d).
    """
    user = authenticate_user(db, payload.username, payload.password, payload.tenant_id)
    if not user:
        raise HTTPException(401, "Incorrect username or password")
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(db, user)
    return schemas.TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        role=user.role,
        username=user.username,
        full_name=user.full_name,
        tenant_id=user.tenant_id,
        shop_name=user.tenant.shop_name,
    )


@router.post("/refresh", response_model=schemas.TokenResponse)
def refresh_token(payload: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Priority 2a: Silent refresh flow.
    The frontend calls this on any 401 before redirecting to /login.
    Returns a new access_token. The refresh_token itself is NOT rotated
    (no revoke-on-use) so the client doesn't need to update its stored
    refresh_token on every refresh call — simpler for the frontend.
    Explicit revocation is available via DELETE /auth/logout.
    """
    user = verify_refresh_token(db, payload.refresh_token)
    if not user:
        raise HTTPException(401, "Refresh token is invalid, expired, or revoked — please log in again")

    new_access_token = create_access_token(user)
    return schemas.TokenResponse(
        access_token=new_access_token,
        refresh_token=payload.refresh_token,   # same refresh token, not rotated
        role=user.role,
        username=user.username,
        full_name=user.full_name,
        tenant_id=user.tenant_id,
        shop_name=user.tenant.shop_name,
    )


@router.delete("/logout")
def logout(payload: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Explicit logout: revokes the provided refresh token so it can't be
    used to silently refresh access anymore. The access token itself is
    short-lived (12h) and will naturally expire.
    """
    revoked = revoke_refresh_token(db, payload.refresh_token)
    return {"revoked": revoked}


@router.delete("/logout-all")
def logout_all(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revokes ALL refresh tokens for the current user — 'log out everywhere'."""
    count = revoke_all_tokens_for_user(db, current_user.id)
    return {"revoked_count": count}


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(current_user: models.User = Depends(require_owner), db: Session = Depends(get_db)):
    """Owner-only: see every account (Owner + Staff) on the system."""
    return db.query(models.User).order_by(models.User.created_at).all()


@router.post("/users", response_model=schemas.UserOut)
def create_user(
    payload: schemas.CreateUserRequest,
    current_user: models.User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """Owner-only: create a new Staff (or additional Owner) account."""
    existing = db.query(models.User).filter(models.User.username == payload.username, models.User.tenant_id == current_user.tenant_id).first()
    if existing:
        raise HTTPException(400, "That username is already taken")

    user = models.User(
        tenant_id=current_user.tenant_id,
        username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/deactivate", response_model=schemas.UserOut)
def deactivate_user(
    user_id: int,
    current_user: models.User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """Owner-only: disable a Staff account (e.g. employee left) without deleting their history."""
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == current_user.id:
        raise HTTPException(400, "You can't deactivate your own account")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user