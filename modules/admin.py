# modules/admin.py

from modules.jwt_auth import get_current_user
from modules.auth_dependency import require_admin
from fastapi import APIRouter, Depends
from config.redis_client import redis_client
from config.db_pool import get_gasman_db




router = APIRouter(prefix="/admin", tags=["Admin"])


# =====================================================
# 🔹 EXISTING REDIS-BASED ENDPOINTS (KEEP)
# =====================================================

@router.get("/locations")
def locations(_: dict = Depends(require_admin)):
    """
    Live device locations from Redis
    Used by legacy / lightweight views
    """
    return [
        redis_client.hgetall(key)
        for key in redis_client.scan_iter("device:*")
    ]


@router.get("/device/{device_id}")
def device(device_id: str, _: dict = Depends(require_admin)):
    """
    Single device snapshot from Redis
    """
    return redis_client.hgetall(f"device:{device_id}")


# =====================================================
# 🟢 DASHBOARD KPI SUMMARY (NEW – DB SOURCE OF TRUTH)
# =====================================================

@router.get("/dashboard/summary")
def dashboard_summary(_: dict = Depends(require_admin)):
    """
    Admin dashboard KPIs
    SINGLE SOURCE OF TRUTH (DB)
    """
    db = get_gasman_db()
    cur = db.cursor(dictionary=True)

    try:
        # -------------------------------
        # Active Tasks
        # -------------------------------
        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM gasman_tasks
            WHERE status IN ('ACCEPTED','IN_PROGRESS')
        """)
        active_tasks = cur.fetchone()["cnt"]

        # -------------------------------
        # Device States
        # -------------------------------
        cur.execute("""
            SELECT
                SUM(classification = 'CRITICAL') AS critical_devices,
                SUM(classification = 'LOW')      AS low_devices,
                SUM(system_status = 'OFFLINE')   AS offline_devices
            FROM gasman_device_status
        """)
        row = cur.fetchone() or {}

        return {
            "active_tasks": active_tasks or 0,
            "critical_devices": row.get("critical_devices") or 0,
            "low_devices": row.get("low_devices") or 0,
            "offline_devices": row.get("offline_devices") or 0
        }

    finally:
        cur.close()
        db.close()
@router.get("/live")
def admin_live_page(
    request: Request,
    user: dict = Depends(require_admin)
):
    return templates.TemplateResponse(
        "admin_live.html",
        {
            "request": request,
            "user_name": user["sub"],
            "role": user["role"]
        }
    )
