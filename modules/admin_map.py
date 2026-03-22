# modules/admin_map.py
"""
ADMIN LIVE MAP API – GASMAN (INDUSTRIAL VERSION)
------------------------------------------------
✔ Single-query device load
✔ Includes customer_name + device address
✔ Single-query task + latest driver location
✔ No N+1 queries
✔ Correct table: gasman_user_location_history
✔ Includes FILLING + FILLED
✔ KPI filter supported
✔ Production safe
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from config.db_pool import get_gasman_db
from modules.auth_dependency import require_admin
from decimal import Decimal
import traceback

router = APIRouter(prefix="/admin/map", tags=["Admin Map"])


# =========================================================
# SAFE FLOAT
# =========================================================

def _safe_float(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except Exception:
        return None


# =========================================================
# LIVE MAP
# =========================================================

@router.get("/live")
def admin_live_map(
    request: Request,
    _: dict = Depends(require_admin)
):

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    try:

        # -------------------------------------------------
        # FILTER
        # -------------------------------------------------

        flt = request.query_params.get("filter")

        where = ["g.coordinates IS NOT NULL"]

        if flt == "CRITICAL":
            where.append("g.classification = 'CRITICAL'")
        elif flt == "LOW":
            where.append("g.classification = 'LOW'")
        elif flt == "OFFLINE":
            where.append("g.online = 0")

        where_sql = " AND ".join(where)

        # -------------------------------------------------
        # DEVICES (WITH CUSTOMER + ADDRESS)
        # -------------------------------------------------

        cur.execute(f"""
            SELECT
                g.device_id,
                g.classification,
                g.gas_percentage,
                g.coordinates,
                g.online,
                d.customer_name,
                d.address
            FROM gasman_device_status g
            LEFT JOIN data_logger.devicelist d
                ON d.device_id = g.device_id
            WHERE {where_sql}
        """)

        rows = cur.fetchall()

        devices = []

        for r in rows:

            coords = str(r["coordinates"]).replace(" ", "")

            devices.append({
                "device_id": r["device_id"],
                "classification": r["classification"],
                "gas_percent": _safe_float(r["gas_percentage"]),
                "offline": not bool(r["online"]),
                "coordinates": coords,
                "customer_name": r.get("customer_name"),
                "device_location": r.get("address")
            })

        # -------------------------------------------------
        # TASKS + GAS % + LATEST DRIVER LOCATION
        # -------------------------------------------------

        cur.execute("""
            SELECT
                t.id AS task_id,
                t.device_id,
                t.accepted_by AS user_name,
                t.status,
                t.tracking_id,

                d.customer_name,
                d.address,

                g.coordinates AS device_coordinates,
                g.gas_percentage,

                ul.lat,
                ul.lng,
                ul.recorded_at

            FROM gasman_tasks t

            JOIN gasman_device_status g
                ON g.device_id = t.device_id

            LEFT JOIN data_logger.devicelist d
                ON d.device_id = t.device_id

            LEFT JOIN (
                SELECT u1.user_name,
                       u1.lat,
                       u1.lng,
                       u1.recorded_at
                FROM gasman_user_location_history u1
                JOIN (
                    SELECT user_name,
                           MAX(recorded_at) AS max_time
                    FROM gasman_user_location_history
                    GROUP BY user_name
                ) u2
                ON u1.user_name = u2.user_name
                AND u1.recorded_at = u2.max_time
            ) ul
                ON ul.user_name = t.accepted_by

            WHERE (
    t.status IN ('ASSIGNED','EN_ROUTE','ON_SITE','FILLING','FILLED')
    OR (
        t.status = 'COMPLETED'
        AND ul.recorded_at > NOW() - INTERVAL 5 MINUTE
    )
)        """)

        task_rows = cur.fetchall()

        tasks = []

        for t in task_rows:

            tasks.append({
                "task_id": t["task_id"],
                "device_id": t["device_id"],
                "customer_name": t["customer_name"],
                "device_location": t["address"],
                "user_name": t["user_name"],
                "status": t["status"],
                "tracking_id": t["tracking_id"],
                "device_coordinates": t["device_coordinates"],
                "user_lat": _safe_float(t["lat"]),
                "user_lng": _safe_float(t["lng"]),
                "gas_percent": _safe_float(t["gas_percentage"]),
                "last_update": t["recorded_at"]
            })

        return {
            "devices": devices,
            "tasks": tasks
        }

    except Exception as e:

        traceback.print_exc()

        return JSONResponse(
            status_code=200,
            content={
                "devices": [],
                "tasks": [],
                "error": str(e)
            }
        )

    finally:

        cur.close()
        conn.close()
