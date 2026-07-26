from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.deps import get_current_user, require_owner
from app.services.auth_service import authenticate_user, create_access_token, hash_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(401, "Incorrect username or password")
    token = create_access_token(user)
    return schemas.TokenResponse(
        access_token=token, role=user.role, username=user.username, full_name=user.full_name,
    )


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
    existing = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing:
        raise HTTPException(400, "That username is already taken")

    user = models.User(
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
    user = db.query(models.User).get(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == current_user.id:
        raise HTTPException(400, "You can't deactivate your own account")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user