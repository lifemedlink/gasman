# modules/jwt_auth.py

from fastapi import Request, HTTPException, status
from config.jwt_handler import verify_token
from config.redis_client import redis_client
import logging

log = logging.getLogger("gasman.jwt")


def get_current_user(request: Request):

    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required"
        )

    payload = verify_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired"
        )

    username = payload.get("sub")
    session_id = payload.get("sid")

    if not username or not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    # 🔐 Validate DB-backed session via Redis
    redis_key = f"user:{username}:session"
    active_session = redis_client.get(redis_key)

    if active_session != session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Logged in from another device"
        )

    return payload
