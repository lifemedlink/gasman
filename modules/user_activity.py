# modules/user_activity.py
"""
GASMAN – USER ACTIVITY (FINAL / INDUSTRIAL)

✔ Uses GASMAN DB pool
✔ Strict user ownership validation
✔ JWT-secured
✔ Decimal + datetime safe
✔ Clean timeline formatting
✔ No undefined variables
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from config.db_pool import get_gasman_db
from modules.jwt_auth import get_current_user
from modules.auth_dependency import require_login
from decimal import Decimal
from datetime import datetime

router = APIRouter(prefix="/user/activity", tags=["User Activity"])


# =====================================================
# HELPERS
# =====================================================

def fmt_value(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return v


def fmt_row(row: dict):
    return {k: fmt_value(v) for k, v in row.items()}


# =====================================================
# LIST COMPLETED TASKS BY DATE
# =====================================================

@router.get("/list")
def activity_list(
    date: str,
    user_payload: dict = Depends(get_current_user),
    _: dict = Depends(require_login)
):
    username = user_payload["sub"]

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute("""
            SELECT
                id AS task_id,
                device_id,
                tracking_id,
                status,
                completed_at
            FROM gasman_tasks
            WHERE accepted_by = %s
              AND status = 'COMPLETED'
              AND DATE(completed_at) = %s
            ORDER BY completed_at DESC
        """, (username, date))

        rows = cur.fetchall()
        return [fmt_row(r) for r in rows]

    finally:
        cur.close()
        conn.close()


# =====================================================
# TASK DETAIL (TIMELINE)
# =====================================================

@router.get("/{task_id}")
def activity_detail(
    task_id: int,
    user_payload: dict = Depends(get_current_user),
    _: dict = Depends(require_login)
):
    username = user_payload["sub"]

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    try:
        # --------------------------------------------------
        # Validate ownership + completed
        # --------------------------------------------------
        cur.execute("""
            SELECT device_id, tracking_id, status
            FROM gasman_tasks
            WHERE id = %s
              AND accepted_by = %s
              AND status = 'COMPLETED'
        """, (task_id, username))

        task = cur.fetchone()

        if not task:
            raise HTTPException(404, "Task not found")

        # --------------------------------------------------
        # Timeline
        # --------------------------------------------------
        cur.execute("""
            SELECT
                action,
                note,
                DATE_FORMAT(created_at, '%H:%i') AS tm
            FROM gasman_task_activity
            WHERE task_id = %s
            ORDER BY created_at
        """, (task_id,))

        rows = cur.fetchall()

        # --------------------------------------------------
        # Deduplicate timeline entries
        # --------------------------------------------------
        seen = set()
        timeline = []

        for r in rows:
            key = (r["tm"], r["note"])
            if key in seen:
                continue
            seen.add(key)

            icon = {
                "ASSIGNED": "🕒",
                "EN_ROUTE": "🧭",
                "ON_SITE": "📍",
                "COMPLETED": "✅"
            }.get(r["action"], "•")

            timeline.append({
                "time": r["tm"],
                "label": f"{icon} {r['note']}"
            })

        return {
            "device_id": task["device_id"],
            "tracking_id": task["tracking_id"],
            "status": task["status"],
            "timeline": timeline
        }

    finally:
        cur.close()
        conn.close()
