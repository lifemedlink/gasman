# modules/history.py
"""
GASMAN – DEVICE & TASK HISTORY (FINAL / 2-DB SAFE)
---------------------------------------------------
✔ Uses GASMAN DB only
✔ Role-based filtering
✔ Admin/Subadmin → all devices
✔ User (driver) → own completed tasks only
✔ Date range support
✔ Decimal-safe JSON
✔ Production hardened
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from modules.jwt_auth import get_current_user
from config.db_pool import get_gasman_db
from decimal import Decimal
from datetime import datetime
import logging

router = APIRouter(prefix="/history", tags=["History"])
log = logging.getLogger("gasman.history")


# =====================================================
# HELPERS
# =====================================================

def fmt(row):
    """Convert Decimal & datetime safely"""
    out = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, datetime):
            out[k] = v.strftime("%Y-%m-%d %H:%M:%S")
        else:
            out[k] = v
    return out


# =====================================================
# ADMIN / SUBADMIN HISTORY
# =====================================================

@router.get("/admin")
def get_history_admin(
    user: dict = Depends(get_current_user),
    device_id: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    limit: int = Query(500, le=5000)
):
    """
    Admin/Subadmin:
    - Full device history
    - Includes gas %, tracking_id, driver
    """

    role = (user.get("role") or "").lower()
    if role not in ("admin", "subadmin"):
        raise HTTPException(403, "Unauthorized")

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    try:
        sql = """
            SELECT
                h.device_id,
                h.gas_percentage,
                h.classification,
                h.event_time,
                t.user_name,
                t.tracking_id,
                t.status
            FROM gasman_history h
            LEFT JOIN gasman_tasks t
                ON t.device_id = h.device_id
               AND t.status = 'COMPLETED'
            WHERE 1=1
        """
        params = []

        if device_id:
            sql += " AND h.device_id = %s"
            params.append(device_id)

        if start_date:
            sql += " AND h.event_time >= %s"
            params.append(start_date + " 00:00:00")

        if end_date:
            sql += " AND h.event_time <= %s"
            params.append(end_date + " 23:59:59")

        sql += " ORDER BY h.event_time DESC LIMIT %s"
        params.append(limit)

        cur.execute(sql, params)
        rows = cur.fetchall()

        return JSONResponse([fmt(r) for r in rows])

    finally:
        cur.close()
        conn.close()


# =====================================================
# USER HISTORY (DRIVER ONLY)
# =====================================================

@router.get("/user")
def get_user_history(
    user: dict = Depends(get_current_user),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    limit: int = Query(200, le=2000)
):
    """
    Driver:
    - Only completed tasks handled by driver
    - Shows tracking_id proof
    """

    role = (user.get("role") or "").lower()
    if role != "user":
        raise HTTPException(403, "Only drivers allowed")

    username = user.get("sub")

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    try:
        sql = """
            SELECT
                h.device_id,
                h.gas_percentage,
                h.classification,
                h.event_time,
                t.tracking_id
            FROM gasman_tasks t
            JOIN gasman_history h
                ON h.device_id = t.device_id
            WHERE t.user_name = %s
              AND t.status = 'COMPLETED'
        """
        params = [username]

        if start_date:
            sql += " AND h.event_time >= %s"
            params.append(start_date + " 00:00:00")

        if end_date:
            sql += " AND h.event_time <= %s"
            params.append(end_date + " 23:59:59")

        sql += " ORDER BY h.event_time DESC LIMIT %s"
        params.append(limit)

        cur.execute(sql, params)
        rows = cur.fetchall()

        return JSONResponse([fmt(r) for r in rows])

    finally:
        cur.close()
        conn.close()
