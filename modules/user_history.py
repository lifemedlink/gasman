# modules/user_history.py
"""
GASMAN – USER HISTORY API
--------------------------------
✔ Uses GASMAN DB pool
✔ JWT secured
✔ Completed / Cancelled tasks
✔ Filterable by status
✔ Safe duration calculation
✔ Production safe
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from config.db_pool import get_gasman_db
from modules.jwt_auth import get_current_user
from modules.auth_dependency import require_login
from datetime import datetime
from decimal import Decimal

router = APIRouter(
    prefix="/api/user/history",
    tags=["User History"]
)


# =========================================================
# HELPER – FORMAT ROW
# =========================================================
def format_row(row: dict):
    formatted = {}

    for k, v in row.items():
        if isinstance(v, Decimal):
            formatted[k] = float(v)
        elif isinstance(v, datetime):
            formatted[k] = v.strftime("%Y-%m-%d %H:%M:%S")
        else:
            formatted[k] = v

    return formatted


# =========================================================
# GET USER HISTORY
# =========================================================
@router.get("")
def get_user_history(
    status: str | None = Query(None),
    limit: int = Query(100, le=500),
    user: dict = Depends(get_current_user),
    _: dict = Depends(require_login)
):
    """
    Returns completed / cancelled jobs for logged-in driver.
    """

    if isinstance(user, JSONResponse):
        return user

    username = user.get("sub")

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    try:
        sql = """
            SELECT
                id AS task_id,
                tracking_id,
                device_id,
                status,
                accepted_at,
                completed_at,
                CASE
                    WHEN completed_at IS NOT NULL
                    THEN TIMESTAMPDIFF(
                        MINUTE,
                        accepted_at,
                        completed_at
                    )
                    ELSE NULL
                END AS duration_minutes
            FROM gasman_tasks
            WHERE accepted_by = %s
              AND status IN ('COMPLETED','CANCELLED')
        """

        params = [username]

        if status:
            sql += " AND status = %s"
            params.append(status)

        sql += " ORDER BY accepted_at DESC LIMIT %s"
        params.append(limit)

        cur.execute(sql, params)
        rows = cur.fetchall()

        return [format_row(r) for r in rows]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cur.close()
        conn.close()
