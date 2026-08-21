"""
Password hashing + JWT issuing/verification for the Owner/Staff login
system.

Priority 2a additions:
  - Refresh token flow: create_refresh_token() / verify_refresh_token() /
    revoke_refresh_token(). The raw UUID4 token is returned to the client;
    only its SHA-256 hash is stored in the RefreshToken table (same
    principle as password hashing — never store a credential that can be
    reused if the DB is compromised).
  - Access tokens now expire in jwt_expire_minutes (12h by default).
    Refresh tokens expire in refresh_token_expire_days (30d by default).
    On 401, the frontend silently calls POST /auth/refresh first; only
    if that also fails does it redirect to /login.
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app import models

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def authenticate_user(db: Session, username: str, password: str) -> Optional[models.User]:
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(user: models.User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Refresh token support (Priority 2a)
# ---------------------------------------------------------------------------

def _hash_token(raw_token: str) -> str:
    """SHA-256 hash of the raw token string — stored in the DB, never the raw value."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_refresh_token(db: Session, user: models.User) -> str:
    """
    Generates a new refresh token (UUID4), stores its hash in the DB with
    an expiry date, and returns the raw token to be sent to the client.

    The raw token is NEVER stored — only its hash — so a DB compromise
    doesn't immediately yield usable refresh tokens.
    """
    raw = str(uuid.uuid4())
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)

    token_row = models.RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(raw),
        expires_at=expires,
        revoked=False,
    )
    db.add(token_row)
    db.commit()
    return raw


def verify_refresh_token(db: Session, raw_token: str) -> Optional[models.User]:
    """
    Validates a refresh token. Returns the associated User if valid,
    None if expired, revoked, or not found.

    Does NOT revoke the token — the caller (auth router's /refresh endpoint)
    decides whether to revoke-and-reissue (rotation) or keep the same token.
    For this implementation we do NOT rotate (no revoke-on-use) to keep the
    client simple, but the revoked field is there for explicit logout/revocation.
    """
    token_hash = _hash_token(raw_token)
    token_row = (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.token_hash == token_hash,
            models.RefreshToken.revoked.is_(False),
            models.RefreshToken.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    if not token_row:
        return None

    user = db.get(models.User, token_row.user_id)
    if not user or not user.is_active:
        return None
    return user


def revoke_refresh_token(db: Session, raw_token: str) -> bool:
    """
    Revokes a specific refresh token (e.g. on explicit logout from a device).
    Returns True if found and revoked, False if not found.
    """
    token_hash = _hash_token(raw_token)
    token_row = (
        db.query(models.RefreshToken)
        .filter(models.RefreshToken.token_hash == token_hash)
        .first()
    )
    if not token_row:
        return False
    token_row.revoked = True
    db.commit()
    return True


def revoke_all_tokens_for_user(db: Session, user_id: int) -> int:
    """
    Revokes all active refresh tokens for a user — used on password change
    or explicit "log out all devices" action. Returns count revoked.
    """
    count = (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.user_id == user_id,
            models.RefreshToken.revoked.is_(False),
        )
        .update({"revoked": True}, synchronize_session=False)
    )
    db.commit()
    return count