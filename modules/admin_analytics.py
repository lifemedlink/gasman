from fastapi import Depends
from modules.jwt_auth import get_current_user
# modules/admin_analytics.py
"""
ADMIN ANALYTICS – DEVICE LIVE VIEW
----------------------------------
✔ DB-driven (gasman_device_status = source of truth)
✔ Decimal-safe
✔ JSON-safe
✔ Used by Admin dashboard & map info cards
"""

from fastapi import APIRouter, Depends
from config.db_pool import get_gasman_db
from modules.auth_dependency import require_admin
from datetime import datetime
from decimal import Decimal

router = APIRouter(prefix="/admin", tags=["Admin Analytics"])


# -----------------------------
# Helpers
# -----------------------------
def _safe_float(v):
    """Convert Decimal / numeric to float safely"""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except Exception:
        return None


# -----------------------------
# DEVICE LIVE VIEW
# -----------------------------
@router.get("/device/{device_id}")
def get_device_live(device_id: str, _: dict = Depends(require_admin)):
    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    try:
        # ==========================================
        # DEVICE STATUS (SINGLE SOURCE OF TRUTH)
        # ==========================================
        cur.execute("""
            SELECT
                g.device_id,
                g.gas_percentage,
                g.classification,
                g.coordinates,
                g.last_log_time AS updated_at,
                g.system_status,
                dl.customer_name
            FROM gasman_device_status g
            LEFT JOIN data_logger.devicelist dl ON dl.device_id = g.device_id
            WHERE g.device_id = %s
            LIMIT 1
        """, (device_id,))
        row = cur.fetchone()

        if not row:
            return {}

        # ==========================================
        # ACTIVE TASK (OPTIONAL)
        # ==========================================
        cur.execute("""
            SELECT user_name, tracking_id, status
            FROM gasman_tasks
            WHERE device_id = %s
              AND status IN ('ACCEPTED','IN_PROGRESS')
            ORDER BY created_at DESC
            LIMIT 1
        """, (device_id,))
        task = cur.fetchone()

        # ==========================================
        # GPS PARSE (SAFE)
        # ==========================================
        lat, lng = None, None
        coords = row.get("coordinates")
        if coords:
            try:
                lat, lng = map(float, coords.replace(" ", "").split(","))
            except Exception:
                pass

        # ==========================================
        # FINAL RESPONSE (FRONTEND SAFE)
        # ==========================================
        return {
            "device_id": row["device_id"],
            "customer_name": row.get("customer_name") or "-",

            "assigned_user": task["user_name"] if task else None,
            "tracking_id": task["tracking_id"] if task else None,

            "gas_percentage": _safe_float(row["gas_percentage"]),
            "status": row["classification"],
            "system_status": row["system_status"],

            "latitude": lat,
            "longitude": lng,

            "updated_at": (
                row["updated_at"].isoformat()
                if isinstance(row["updated_at"], datetime)
                else row["updated_at"]
            )
        }

    finally:
        cur.close()
        conn.close()
