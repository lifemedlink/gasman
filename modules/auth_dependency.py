# modules/auth_dependency.py

"""
GASMAN – STRICT SINGLE DEVICE AUTH DEPENDENCY
---------------------------------------------
✔ JWT validation
✔ Redis single-session enforcement
✔ DB session validation
✔ Sliding expiration
✔ Force logout enforcement
✔ Production-safe
"""

from fastapi import Request
from fastapi.responses import RedirectResponse
from config.jwt_handler import verify_token
from config.redis_client import redis_client
from config.db_pool import get_gasman_db

SESSION_TTL_SECONDS = 28800  # 8 hours


# =========================================================
# GET CURRENT USER
# =========================================================
def get_current_user(request: Request):

    access_token = request.cookies.get("access_token")

    if not access_token:
        return RedirectResponse("/login?msg=Login required", status_code=302)

    payload = verify_token(access_token)

    if not payload:
        return RedirectResponse("/login?msg=Session expired", status_code=302)

    username = payload.get("sub")
    role = payload.get("role")
    sid = payload.get("sid")
    user_id = payload.get("uid")   # 🔥 FIXED (was wrong before)

    if not username or not sid:
        return RedirectResponse("/login?msg=Invalid session", status_code=302)

    # =====================================================
    # 1️⃣ Redis Session Validation (Strict Single Device)
    # =====================================================
    redis_key = f"user:{username}:session"
    active_session = redis_client.get(redis_key)

    if not active_session or active_session != sid:
        return RedirectResponse(
            "/login?msg=session_expired",
            status_code=302
        )

    # 🔥 Sliding expiration (VERY IMPORTANT)
    redis_client.expire(redis_key, SESSION_TTL_SECONDS)

    # =====================================================
    # 2️⃣ DB Session Validation (Force Logout Enforcement)
    # =====================================================
    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute("""
            SELECT 1
            FROM gasman.gasman_user_sessions
            WHERE data_logger_user_id = %s
              AND session_id = %s
            LIMIT 1
        """, (user_id, sid))

        session_exists = cur.fetchone()

        if not session_exists:
            redis_client.delete(redis_key)
            return RedirectResponse(
                "/login?msg=Session invalidated",
                status_code=302
            )

    finally:
        cur.close()
        conn.close()

    return payload


# =========================================================
# REQUIRE ADMIN
# =========================================================
def require_admin(request: Request):

    user = get_current_user(request)

    if isinstance(user, RedirectResponse):
        return user

    if user.get("role") not in ("admin", "subadmin"):
        return RedirectResponse("/login?msg=Unauthorized", status_code=302)

    return user


# =========================================================
# REQUIRE LOGIN
# =========================================================
def require_login(request: Request):

    user = get_current_user(request)

    if isinstance(user, RedirectResponse):
        return user

    return user
