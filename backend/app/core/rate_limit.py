from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request
import jwt
from app.config import settings

def custom_key_func(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except Exception:
            pass
    return get_remote_address(request)

limiter = Limiter(key_func=custom_key_func, default_limits=[settings.rate_limit_global])
