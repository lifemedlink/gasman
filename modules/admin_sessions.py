# modules/admin_sessions.py

"""
GASMAN – ADMIN SESSION MANAGEMENT
----------------------------------
✔ Uses dual DB pools
✔ data_logger → user_details
✔ gasman → gasman_user_sessions
✔ No backward compatibility
✔ WebSocket force logout
✔ Production safe
"""

from fastapi import APIRouter, Depends, HTTPException
from modules.auth_dependency import require_admin
from config.db_pool import get_data_logger_db, get_gasman_db
from ws.session_ws import send_force_logout
import logging

router = APIRouter(prefix="/admin/sessions", tags=["Admin Sessions"])
log = logging.getLogger("gasman.admin_sessions")


# =========================================================
# LIST ACTIVE SESSIONS
# =========================================================
@router.get("/active")
def list_active_sessions(_: dict = Depends(require_admin)):

    gasman_conn = get_gasman_db()
    data_logger_conn = get_data_logger_db()

    try:
        gas_cur = gasman_conn.cursor(dictionary=True)

        # Fetch all active sessions from GASMAN DB
        gas_cur.execute("""
            SELECT
                data_logger_user_id,
                ip_address,
                user_agent,
                last_seen,
                created_at,
                expires_at
            FROM gasman_user_sessions
            ORDER BY last_seen DESC
        """)

        sessions = gas_cur.fetchall()
        gas_cur.close()

        if not sessions:
            return []

        # Collect user_ids
        user_ids = [s["data_logger_user_id"] for s in sessions]

        # Fetch usernames from DATA_LOGGER DB
        dl_cur = data_logger_conn.cursor(dictionary=True)

        format_strings = ",".join(["%s"] * len(user_ids))

        dl_cur.execute(f"""
            SELECT user_id, user_name
            FROM user_details
            WHERE user_id IN ({format_strings})
        """, tuple(user_ids))

        users = dl_cur.fetchall()
        dl_cur.close()

        user_map = {u["user_id"]: u["user_name"] for u in users}

        # Merge data
        result = []
        for s in sessions:
            result.append({
                "user_name": user_map.get(s["data_logger_user_id"], "UNKNOWN"),
                "ip_address": s["ip_address"],
                "user_agent": s["user_agent"],
                "last_seen": s["last_seen"],
                "created_at": s["created_at"],
                "expires_at": s["expires_at"]
            })

        return result

    finally:
        gasman_conn.close()
        data_logger_conn.close()


# =========================================================
# FORCE LOGOUT USER
# =========================================================
@router.delete("/force/{username}")
async def force_logout(username: str, _: dict = Depends(require_admin)):

    gasman_conn = get_gasman_db()
    data_logger_conn = get_data_logger_db()

    try:
        # 1️⃣ Get user_id from data_logger
        dl_cur = data_logger_conn.cursor(dictionary=True)
        dl_cur.execute("""
            SELECT user_id
            FROM user_details
            WHERE user_name = %s
            LIMIT 1
        """, (username,))
        user = dl_cur.fetchone()
        dl_cur.close()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user_id = user["user_id"]

        # 2️⃣ Delete session from gasman
        gas_cur = gasman_conn.cursor()
        gas_cur.execute("""
            DELETE FROM gasman_user_sessions
            WHERE data_logger_user_id = %s
        """, (user_id,))

        affected = gas_cur.rowcount
        gasman_conn.commit()
        gas_cur.close()

        if affected == 0:
            raise HTTPException(status_code=404, detail="User not logged in")

        # 3️⃣ Notify via WebSocket
        await send_force_logout(username)

        return {
            "success": True,
            "message": f"{username} logged out successfully"
        }

    finally:
        gasman_conn.close()
        data_logger_conn.close()
