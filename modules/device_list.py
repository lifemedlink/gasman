# modules/device_list.py
"""
GASMAN – DEVICE LIST (DRIVER VIEW)

✔ JWT secured
✔ Uses dual DB pools
✔ Hides devices locked by other drivers
✔ Shows own active task
✔ Production safe
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from config.db_pool import get_gasman_db, get_data_logger_db
from modules.jwt_auth import get_current_user
from decimal import Decimal
from datetime import datetime

router = APIRouter(prefix="/devices", tags=["Device List"])


# =====================================================
# HELPERS
# =====================================================

def fmt(row):
    out = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


# =====================================================
# DRIVER DEVICE LIST
# =====================================================

@router.get("/list")
def device_list(user: dict = Depends(get_current_user)):

    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    username = user["sub"]
    role = user.get("role", "").lower()

    # Only drivers allowed
    if role != "user":
        return JSONResponse({"error": "only drivers allowed"}, status_code=403)

    gasman_conn = get_gasman_db()
    data_logger_conn = get_data_logger_db()

    try:
        gcur = gasman_conn.cursor(dictionary=True)
        dcur = data_logger_conn.cursor(dictionary=True)

        # =====================================================
        # DRIVER ACTIVE TASK (IF ANY)
        # =====================================================
        gcur.execute("""
            SELECT device_id, status
            FROM gasman_tasks
            WHERE accepted_by = %s
              AND status IN ('ASSIGNED','EN_ROUTE','ON_SITE')
            LIMIT 1
        """, (username,))

        own_task = gcur.fetchone()
        own_device_id = own_task["device_id"] if own_task else None
        own_task_status = own_task["status"] if own_task else None

        # =====================================================
        # DEVICES LOCKED BY OTHER DRIVERS
        # =====================================================
        gcur.execute("""
            SELECT DISTINCT device_id
            FROM gasman_tasks
            WHERE status IN ('ASSIGNED','EN_ROUTE','ON_SITE')
        """)
        locked_devices = {r["device_id"] for r in gcur.fetchall()}

        # =====================================================
        # LIVE DEVICE STATUS (FROM GASMAN DB)
        # =====================================================
        gcur.execute("""
            SELECT
                device_id,
                gas_percentage,
                classification,
                online,
                last_log_time
            FROM gasman_device_status
            ORDER BY device_id
        """)
        status_rows = gcur.fetchall()

        # =====================================================
        # DEVICE DETAILS (FROM DATA_LOGGER DB)
        # =====================================================
        dcur.execute("""
            SELECT
                device_id,
                customer_name,
                address,
                coordinates
            FROM devicelist
        """)
        device_meta = {
            r["device_id"]: r
            for r in dcur.fetchall()
        }

        devices = []

        for r in status_rows:
            device_id = r["device_id"]

            # Hide devices locked by others
            if device_id in locked_devices and device_id != own_device_id:
                continue

            meta = device_meta.get(device_id, {})

            devices.append({
                "device_id": device_id,
                "customer_name": meta.get("customer_name"),
                "address": meta.get("address"),
                "coordinates": meta.get("coordinates"),

                "gas_percent": float(r["gas_percentage"] or 0),
                "classification": r["classification"],
                "offline": not bool(r["online"]),
                "last_log_time": (
                    r["last_log_time"].isoformat()
                    if r["last_log_time"] else None
                ),

                "is_own_task": device_id == own_device_id,
                "task_status": own_task_status if device_id == own_device_id else None
            })

        return devices

    finally:
        try:
            gcur.close()
            dcur.close()
            gasman_conn.close()
            data_logger_conn.close()
        except Exception:
            pass
