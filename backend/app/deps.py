"""
Reusable FastAPI dependencies for auth. Add `Depends(get_current_user)` to
any route that needs a logged-in user, or `Depends(require_owner)` to any
route that only the shop Owner should be able to use (Analytics, GST
reports, editing rate-list thresholds, viewing cost prices, etc).
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.services.auth_service import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid, please log in again")

    user = db.query(models.User).get(int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found or disabled")

    return user


def require_owner(current_user: models.User = Depends(get_current_user)) -> models.User:
    """
    Gate for Owner-only endpoints: financial analytics, GST reports, rate
    list edits outside the normal bill-confirm flow, viewing cost prices.
    """
    if current_user.role != "owner":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This section is restricted to the shop Owner.",
        )
    return current_user


def get_current_user_flexible(
    token: str = None,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """
    Same as get_current_user, but ALSO accepts the token as a `?token=`
    query parameter. Needed specifically for the bill image endpoint,
    since an <img src="..."> tag has no way to send an Authorization
    header - the frontend passes the token in the URL for that one case.
    """
    raw_token = token or (credentials.credentials if credentials else None)
    if not raw_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")

    payload = decode_access_token(raw_token)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid, please log in again")

    user = db.query(models.User).get(int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found or disabled")

    return user