# modules/auth.py

"""
GASMAN – STRICT SINGLE DEVICE AUTH MODULE
✔ JWT Authentication
✔ Strict Single Device Enforcement
✔ Redis Binding
✔ DB Session Cleanup
✔ Sliding Expiration Compatible
✔ Production Safe
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from config.db_pool import get_data_logger_db
from config.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_token
)
from config.redis_client import redis_client

import uuid
import logging

router = APIRouter()
log = logging.getLogger("gasman.auth")
templates = Jinja2Templates(directory="templates")

SESSION_TTL_SECONDS = 28800  # 8 hours


# =========================================================
# ROLE NORMALIZATION
# =========================================================
def normalize_role(role: str | None) -> str:
    if not role:
        return "user"

    role = role.strip().lower()

    if role == "admin":
        return "admin"

    if role in ("sub admin", "subadmin"):
        return "subadmin"

    return "user"


# =========================================================
# LOGIN (STRICT SINGLE DEVICE)
# =========================================================
@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    db = get_data_logger_db()

    try:
        cur = db.cursor(dictionary=True)

        # -----------------------------------------------------
        # Fetch User
        # -----------------------------------------------------
        cur.execute("""
            SELECT user_id, user_name, role, password
            FROM data_logger.user_details
            WHERE user_name = %s
            LIMIT 1
        """, (username,))
        row = cur.fetchone()

        if not row or row["password"] != password:
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "msg": "Invalid credentials"},
                status_code=401
            )

        role = normalize_role(row["role"])
        session_id = str(uuid.uuid4())

        user_agent = request.headers.get("user-agent", "unknown")

        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip()
        else:
            ip_address = request.client.host or "unknown"

        fingerprint = f"{row['user_name']}|{ip_address}|{user_agent}"
        fingerprint = fingerprint[:128]

        # -----------------------------------------------------
        # 🔥 STRICT SINGLE DEVICE ENFORCEMENT
        # Remove old session before creating new one
        # -----------------------------------------------------
        cur.execute("""
            DELETE FROM gasman.gasman_user_sessions
            WHERE data_logger_user_id = %s
        """, (row["user_id"],))

        # Insert new session
        cur.execute("""
            INSERT INTO gasman.gasman_user_sessions
            (data_logger_user_id, session_id, device_fingerprint,
             ip_address, user_agent, expires_at)
            VALUES (%s, %s, %s, %s, %s, NOW() + INTERVAL 8 HOUR)
        """, (
            row["user_id"],
            session_id,
            fingerprint,
            ip_address,
            user_agent
        ))

        db.commit()

        # -----------------------------------------------------
        # Redis binding (overwrite previous)
        # -----------------------------------------------------
        redis_key = f"user:{row['user_name']}:session"
        redis_client.set(redis_key, session_id, ex=SESSION_TTL_SECONDS)

        # -----------------------------------------------------
        # Create Tokens
        # -----------------------------------------------------
        access_token = create_access_token({
            "sub": row["user_name"],
            "role": role,
            "sid": session_id,
            "uid": row["user_id"]
        })

        refresh_token = create_refresh_token({
            "sub": row["user_name"],
            "sid": session_id,
            "uid": row["user_id"]
        })

        response = RedirectResponse(
            "/admin" if role in ("admin", "subadmin") else "/user",
            status_code=302
        )

        response.set_cookie("access_token", access_token, httponly=True)
        response.set_cookie("refresh_token", refresh_token, httponly=True)

        return response

    finally:
        db.close()


# =========================================================
# LOGOUT
# =========================================================
@router.get("/logout")
async def logout(request: Request):

    access_token = request.cookies.get("access_token")

    if access_token:
        payload = verify_token(access_token)
        if payload:
            username = payload.get("sub")
            redis_key = f"user:{username}:session"
            redis_client.delete(redis_key)

    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    return response
