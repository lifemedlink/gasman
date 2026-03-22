# config/jwt_handler.py

import os
import jwt
import logging
from datetime import datetime, timedelta, timezone

# =========================================================
# CONFIG
# =========================================================

JWT_SECRET = os.getenv("JWT_SECRET")

if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError(
        "JWT_SECRET is missing or too short. "
        "Use: openssl rand -hex 32 and set it in PM2 env."
    )

JWT_ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 480 #8 hours
REFRESH_TOKEN_EXPIRE_DAYS = 1

log = logging.getLogger("gasman.jwt")


# =========================================================
# CREATE ACCESS TOKEN
# =========================================================
def create_access_token(data: dict) -> str:
    payload = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload.update({
        "exp": expire,
        "type": "access"
    })

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# =========================================================
# CREATE REFRESH TOKEN
# =========================================================
def create_refresh_token(data: dict) -> str:
    payload = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )

    payload.update({
        "exp": expire,
        "type": "refresh"
    })

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# =========================================================
# VERIFY TOKEN
# =========================================================
def verify_token(token: str, expected_type: str | None = None) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )

        if expected_type and payload.get("type") != expected_type:
            log.warning("JWT type mismatch")
            return None

        return payload

    except jwt.ExpiredSignatureError:
        log.warning("JWT verification failed: Signature has expired.")
        return None

    except jwt.InvalidTokenError as e:
        log.warning(f"JWT invalid: {str(e)}")
        return None
