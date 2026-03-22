# modules/user_settings.py
"""
GASMAN – USER SETTINGS (INDUSTRIAL VERSION)
------------------------------------------
✔ GASMAN DB pool
✔ Toggle AUTO / MANUAL
✔ Prevent enabling AUTO if task active
✔ Multiple users safe
✔ DB is single source of truth
✔ Clean JSON responses
✔ Production ready
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from modules.jwt_auth import get_current_user
from modules.auth_dependency import require_login
from config.db_pool import get_gasman_db

router = APIRouter(prefix="/user/settings", tags=["User Settings"])


# ======================================================
# 1️⃣ GET USER SETTINGS
# ======================================================
@router.get("")
def get_user_settings(
    user_payload: dict = Depends(get_current_user),
    _: dict = Depends(require_login)
):
    username = user_payload["sub"]

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute("""
            SELECT task_enabled
            FROM gasman_user_settings
            WHERE user_name = %s
        """, (username,))

        row = cur.fetchone()

        # Default AUTO mode = enabled (1)
        if not row:
            cur.execute("""
                INSERT INTO gasman_user_settings (user_name, task_enabled)
                VALUES (%s, 1)
            """, (username,))
            conn.commit()
            task_enabled = 1
        else:
            task_enabled = row["task_enabled"]

        return {
            "task_enabled": bool(task_enabled),
            "mode": "AUTO" if task_enabled else "MANUAL"
        }

    finally:
        cur.close()
        conn.close()


# ======================================================
# 2️⃣ TOGGLE AUTO / MANUAL
# ======================================================
@router.post("/task-toggle")
def set_task_toggle(
    payload: dict,
    request: Request,
    user_payload: dict = Depends(get_current_user),
    _: dict = Depends(require_login)
):
    username = user_payload["sub"]
    enabled = payload.get("enabled")

    if enabled is None:
        raise HTTPException(status_code=400, detail="enabled field required")

    enabled = bool(enabled)

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    try:
        # --------------------------------------------------
        # 1️⃣ Check ACTIVE TASK (DB is truth)
        # --------------------------------------------------
        cur.execute("""
            SELECT id, device_id, status
            FROM gasman_tasks
            WHERE accepted_by = %s
              AND status IN ('ASSIGNED','EN_ROUTE','ON_SITE')
            ORDER BY id DESC
            LIMIT 1
        """, (username,))

        active_task = cur.fetchone()

        # --------------------------------------------------
        # 2️⃣ Block AUTO enable if active task exists
        # --------------------------------------------------
        if active_task and enabled is True:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Cannot enable AUTO mode while task is active",
                    "active_device": active_task["device_id"],
                    "status": active_task["status"],
                    "mode_locked": True
                }
            )

        # --------------------------------------------------
        # 3️⃣ Update toggle safely
        # --------------------------------------------------
        cur.execute("""
            INSERT INTO gasman_user_settings (user_name, task_enabled)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                task_enabled = VALUES(task_enabled),
                updated_at = NOW()
        """, (username, int(enabled)))

        conn.commit()

        return {
            "task_enabled": enabled,
            "mode": "AUTO" if enabled else "MANUAL",
            "mode_locked": False
        }

    finally:
        cur.close()
        conn.close()
