# modules/admin_users.py

"""
GASMAN – ADMIN USER & DRIVER MANAGEMENT
✔ Driver list
✔ Online / Offline (session-based)
✔ Clean device type detection
✔ Device list per driver
✔ Active sessions
✔ Force logout (DB + Redis)
✔ Production safe
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from config.db_pool import get_gasman_db, get_data_logger_db
from modules.auth_dependency import require_admin

router = APIRouter(prefix="/admin/users", tags=["Admin Users"])


# =====================================================
# DEVICE DETECTION HELPER
# =====================================================
def detect_device(user_agent: str) -> str:
    if not user_agent:
        return "Unknown Device"

    ua = user_agent.lower()

    # Device type
    if "android" in ua:
        device = "Android"
    elif "iphone" in ua:
        device = "iPhone"
    elif "windows" in ua:
        device = "Windows PC"
    elif "mac os" in ua:
        device = "Mac"
    elif "linux" in ua:
        device = "Linux"
    else:
        device = "Unknown"

    # Browser type
    if "chrome" in ua and "edge" not in ua:
        browser = "Chrome"
    elif "safari" in ua and "chrome" not in ua:
        browser = "Safari"
    elif "edge" in ua:
        browser = "Edge"
    elif "firefox" in ua:
        browser = "Firefox"
    else:
        browser = ""

    if browser:
        return f"{device} ({browser})"

    return device

# =====================================================
# DRIVER LIST (Online / Offline + Device Count)
# =====================================================
@router.get("/list")
def list_drivers(_: dict = Depends(require_admin)):

    dl_conn = get_data_logger_db()
    gas_conn = get_gasman_db()

    dl_cur = dl_conn.cursor(dictionary=True)
    gas_cur = gas_conn.cursor(dictionary=True)

    try:
        # ---------------------------------------------
        # Get active sessions
        # ---------------------------------------------
        gas_cur.execute("""
            SELECT DISTINCT data_logger_user_id
            FROM gasman_user_sessions
        """)
        active_sessions = gas_cur.fetchall()

        online_user_ids = {
            int(s["data_logger_user_id"])
            for s in active_sessions
            if s["data_logger_user_id"] is not None
        }

        # ---------------------------------------------
        # Get drivers + device count
        # ---------------------------------------------
        dl_cur.execute("""
            SELECT 
                u.user_id,
                u.user_name,
                u.contact_no,
                COUNT(ud.device_id) AS devices_assigned
            FROM user_details u
            LEFT JOIN user_device_list ud
                ON u.user_id = ud.user_id
            WHERE u.role = 'user'
            GROUP BY u.user_id
            ORDER BY u.user_name ASC
        """)

        drivers = dl_cur.fetchall()

        # Attach online flag
        for d in drivers:
            d["is_online"] = int(d["user_id"]) in online_user_ids

        return jsonable_encoder(drivers)

    finally:
        dl_cur.close()
        gas_cur.close()
        dl_conn.close()
        gas_conn.close()


# =====================================================
# DRIVER DEVICES
# =====================================================
@router.get("/devices/{user_id}")
def get_driver_devices(user_id: int, _: dict = Depends(require_admin)):

    conn = get_data_logger_db()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute("""
            SELECT 
                ud.device_id,
                d.customer_name
            FROM user_device_list ud
            LEFT JOIN devicelist d
                ON ud.device_id = d.device_id
            WHERE ud.user_id = %s
        """, (user_id,))

        return cur.fetchall()

    finally:
        cur.close()
        conn.close()


# =====================================================
# ACTIVE SESSIONS (Clean Device + Real IP)
# =====================================================
@router.get("/sessions")
def list_sessions(_: dict = Depends(require_admin)):

    gas_conn = get_gasman_db()
    dl_conn = get_data_logger_db()

    try:
        gas_cur = gas_conn.cursor(dictionary=True)

        gas_cur.execute("""
            SELECT
                data_logger_user_id,
                ip_address,
                user_agent,
                last_seen
            FROM gasman_user_sessions
            ORDER BY last_seen DESC
        """)

        sessions = gas_cur.fetchall()
        gas_cur.close()

        if not sessions:
            return []

        user_ids = [s["data_logger_user_id"] for s in sessions]

        dl_cur = dl_conn.cursor(dictionary=True)
        format_strings = ",".join(["%s"] * len(user_ids))

        dl_cur.execute(f"""
            SELECT user_id, user_name
            FROM user_details
            WHERE user_id IN ({format_strings})
        """, tuple(user_ids))

        users = dl_cur.fetchall()
        dl_cur.close()

        user_map = {u["user_id"]: u["user_name"] for u in users}

        result = []

        for s in sessions:
            device_type = detect_device(s["user_agent"])

            result.append({
                "user_name": user_map.get(s["data_logger_user_id"], "UNKNOWN"),
               # "ip_address": s["ip_address"],
                "device": device_type,
                "last_seen": s["last_seen"]
            })

        return jsonable_encoder(result)

    finally:
        gas_conn.close()
        dl_conn.close()


# =====================================================
# FORCE LOGOUT (DB + Redis)
# =====================================================
@router.delete("/sessions/force/{username}")
def force_logout(username: str, _: dict = Depends(require_admin)):

    from config.redis_client import redis_client

    gas_conn = get_gasman_db()
    dl_conn = get_data_logger_db()

    try:
        # Resolve user_id
        dl_cur = dl_conn.cursor(dictionary=True)
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

        # Delete DB session
        gas_cur = gas_conn.cursor()
        gas_cur.execute("""
            DELETE FROM gasman_user_sessions
            WHERE data_logger_user_id = %s
        """, (user_id,))
        gas_conn.commit()
        gas_cur.close()

        # Delete Redis session
        redis_key = f"user:{username}:session"
        redis_client.delete(redis_key)

        return {
            "success": True,
            "message": f"{username} logged out successfully"
        }

    finally:
        gas_conn.close()
        dl_conn.close()
