from fastapi import APIRouter, Request, Depends, Query
from config.db_pool import get_gasman_db
from modules.auth_dependency import require_login
from decimal import Decimal
from datetime import datetime

router = APIRouter(prefix="/user/devices", tags=["User Devices"])


# ------------------------------------------------------
# JSON SAFE CONVERTER
# ------------------------------------------------------
def _safe(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return v


# ======================================================
# 1️⃣ DEVICES TAB (LIST VIEW)
# ======================================================
@router.get("/list")
def user_devices_list(user: dict = Depends(require_login)):

    username = user["sub"]

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    # --------------------------------------------
    # 1️⃣ Get manual mode
    # --------------------------------------------
    cur.execute("""
        SELECT task_enabled
        FROM gasman_user_settings
        WHERE user_name = %s
    """, (username,))
    setting = cur.fetchone()

    manual_mode = False
    if setting and setting["task_enabled"] == 0:
        manual_mode = True

    # --------------------------------------------
    # 2️⃣ Device list + my active task
    # --------------------------------------------
    cur.execute("""
        SELECT
            g.device_id,
            d.customer_name,
            g.classification,
            g.gas_percentage,
            g.online,
            g.last_log_time,
            g.device_location,
            g.coordinates,

            (
                SELECT t.status
                FROM gasman_tasks t
                WHERE t.device_id = g.device_id
                  AND t.accepted_by = %s
                  AND t.status IN ('ASSIGNED','EN_ROUTE','ON_SITE')
                ORDER BY t.id DESC
                LIMIT 1
            ) AS my_task_status,

            (
                SELECT t.tracking_id
                FROM gasman_tasks t
                WHERE t.device_id = g.device_id
                  AND t.accepted_by = %s
                  AND t.status IN ('ASSIGNED','EN_ROUTE','ON_SITE')
                ORDER BY t.id DESC
                LIMIT 1
            ) AS my_tracking_id,

            (
                 SELECT t.accepted_by
                 FROM gasman_tasks t
                 WHERE t.device_id = g.device_id
                   AND t.status IN ('ASSIGNED','EN_ROUTE','ON_SITE','FILLING','FILLED')
                 ORDER BY t.id DESC
                 LIMIT 1
             ) AS accepted_by,

            EXISTS (
                SELECT 1
                FROM gasman_tasks t2
                WHERE t2.device_id = g.device_id
                  AND t2.status IN ('ASSIGNED','EN_ROUTE','ON_SITE')
            ) AS task_taken

        FROM data_logger.user_device_list ud
        JOIN data_logger.user_details u
          ON u.user_id = ud.user_id
        JOIN gasman_device_status g
          ON g.device_id = ud.device_id
        JOIN data_logger.devicelist d
          ON d.device_id = ud.device_id

        WHERE u.user_name = %s

        ORDER BY
          g.online DESC,
          g.gas_percentage ASC, 
        FIELD(g.classification,'CRITICAL','LOW','NORMAL')
    """, (username, username, username))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "device_id": r["device_id"],
            "customer_name": r["customer_name"],
            "accepted_by": r["accepted_by"],
            "classification": r["classification"],
            "gas_percentage": float(r["gas_percentage"] or 0),
            "online": bool(r["online"]),
            "device_location": r["device_location"],
            "coordinates": r["coordinates"],
            "task_taken": bool(r["task_taken"]),
            "my_task_status": r["my_task_status"],
            "my_tracking_id": r["my_tracking_id"],
            "manual_mode": manual_mode,
            "last_log_time": r["last_log_time"]
        }
        for r in rows
    ]


# ======================================================
# 2️⃣ MAP PINS (DRIVE TAB)
# ======================================================
@router.get("/map")
def user_map_devices(user: dict = Depends(require_login)):

    username = user["sub"]

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT
            g.device_id,
            g.classification,
            g.gas_percentage,
            g.coordinates,
            g.device_location,
            d.customer_name,

            EXISTS (
                SELECT 1
                FROM gasman_tasks t
                WHERE t.device_id = g.device_id
                  AND t.status IN ('ASSIGNED','EN_ROUTE','ON_SITE','FILLING','FILLED')
            ) AS task_taken

        FROM data_logger.user_device_list ud
        JOIN data_logger.user_details u
          ON u.user_id = ud.user_id
        JOIN gasman_device_status g
          ON g.device_id = ud.device_id
        JOIN data_logger.devicelist d
          ON d.device_id = ud.device_id

        WHERE u.user_name = %s
          AND g.online = 1
          AND (
              g.classification IN ('LOW','CRITICAL')
              OR EXISTS (
                SELECT 1
                FROM gasman_tasks t
                WHERE t.device_id = g.device_id
                  AND t.status IN ('ASSIGNED','EN_ROUTE','ON_SITE','FILLING','FILLED')
              )
          )
          AND g.coordinates IS NOT NULL
    """, (username,))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "device_id": r["device_id"],
            "classification": r["classification"],
            "gas_percentage": _safe(r["gas_percentage"]),
            "coordinates": r["coordinates"],
            "device_location": r["device_location"],
            "customer_name": r["customer_name"],
            "task_taken": bool(r["task_taken"]),
        }
        for r in rows
    ]


# ======================================================
# 3️⃣ NEAREST DEVICE
# ======================================================
@router.get("/nearest")
def nearest_device(
    lat: float = Query(...),
    lng: float = Query(...),
    user: dict = Depends(require_login)
):

    username = user["sub"]

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT
            g.device_id,
            g.classification,
            g.gas_percentage,
            g.coordinates,
            g.device_location,

            CASE g.classification
              WHEN 'CRITICAL' THEN 2
              WHEN 'LOW' THEN 1
              ELSE 0
            END AS priority_weight,

            (
              POW(CAST(SUBSTRING_INDEX(g.coordinates, ',', 1) AS DECIMAL(10,7)) - %s, 2) +
              POW(CAST(SUBSTRING_INDEX(g.coordinates, ',', -1) AS DECIMAL(10,7)) - %s, 2)
            ) AS distance_score

        FROM data_logger.user_device_list ud
        JOIN data_logger.user_details u
          ON u.user_id = ud.user_id
        JOIN gasman_device_status g
          ON g.device_id = ud.device_id

        WHERE u.user_name = %s
          AND g.online = 1
          AND g.classification IN ('CRITICAL','LOW')
          AND g.coordinates IS NOT NULL
          AND NOT EXISTS (
            SELECT 1
            FROM gasman_tasks t
            WHERE t.device_id = g.device_id
              AND t.status IN ('ASSIGNED','EN_ROUTE','ON_SITE')
          )

        ORDER BY priority_weight DESC, distance_score ASC
        LIMIT 1
    """, (lat, lng, username))

    row = cur.fetchone()
    cur.close()
    conn.close()

    return row or {}
# ======================================================
# 4️⃣ MANUAL ACCEPT TASK (DEVICE LIST MODE)
# ======================================================
@router.post("/accept/{device_id}")
def manual_accept_task(
    device_id: str,
    user: dict = Depends(require_login)
):
    username = user["sub"]

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    # --------------------------------------------------
    # 1️⃣ Check manual mode
    # --------------------------------------------------
    cur.execute("""
        SELECT task_enabled
        FROM gasman_user_settings
        WHERE user_name = %s
    """, (username,))
    setting = cur.fetchone()

    if not setting or setting["task_enabled"] == 1:
        cur.close()
        conn.close()
        return {"error": "Manual mode disabled"}

    # --------------------------------------------------
    # 2️⃣ Check device eligible
    # --------------------------------------------------
    cur.execute("""
        SELECT classification, online
        FROM gasman_device_status
        WHERE device_id = %s
    """, (device_id,))
    device = cur.fetchone()

    if not device or device["classification"] not in ("LOW", "CRITICAL") or not device["online"]:
        cur.close()
        conn.close()
        return {"error": "Device not eligible"}

    # --------------------------------------------------
    # 3️⃣ Ensure driver has NO active task
    # --------------------------------------------------
    cur.execute("""
        SELECT id
        FROM gasman_tasks
        WHERE accepted_by = %s
          AND status IN ('ASSIGNED','EN_ROUTE','ON_SITE','FILLING','FILLED')
        LIMIT 1
    """, (username,))

    if cur.fetchone():
        cur.close()
        conn.close()
        return {"error": "You already have an active task"}

    try:
        # --------------------------------------------------
        # 4️⃣ Cancel SYSTEM pending task (manual override)
        # --------------------------------------------------
        cur.execute("""
            UPDATE gasman_tasks
            SET status = 'CANCELLED',
                updated_at = NOW()
            WHERE device_id = %s
              AND status = 'PENDING'
              AND user_name = 'SYSTEM'
        """, (device_id,))

        # --------------------------------------------------
        # 5️⃣ Generate Tracking ID
        # --------------------------------------------------
        cur.execute("SELECT DATE_FORMAT(NOW(), '%Y%m%d') AS dt")
        dt = cur.fetchone()["dt"]

        cur.execute("""
            INSERT INTO tracking_counters (dt, seq)
            VALUES (%s, 1)
            ON DUPLICATE KEY UPDATE seq = seq + 1
        """, (dt,))

        cur.execute("""
            SELECT seq FROM tracking_counters WHERE dt = %s
        """, (dt,))
        seq = cur.fetchone()["seq"]

        tracking_id = f"GM-{dt}-{seq:03d}"

        # --------------------------------------------------
        # 6️⃣ Insert Manual Task
        # --------------------------------------------------
        cur.execute("""
            INSERT INTO gasman_tasks
            (device_id, priority, user_name, accepted_by,
             status, accepted_at, tracking_id, onsite_source)
            VALUES (%s, %s, %s, %s,
                    'ASSIGNED', NOW(), %s, 'MANUAL')
        """, (
            device_id,
            device["classification"],
            username,
            username,
            tracking_id
        ))

        task_id = cur.lastrowid

        # --------------------------------------------------
        # 7️⃣ Activity Log
        # --------------------------------------------------
        cur.execute("""
            INSERT INTO gasman_task_activity
            (task_id, device_id, user_name,
             action, status_after, tracking_id, note)
            VALUES (%s, %s, %s,
                    'MANUAL_ACCEPT', 'ASSIGNED', %s,
                    'Manual task accepted')
        """, (
            task_id,
            device_id,
            username,
            tracking_id
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        cur.close()
        conn.close()
        return {"error": "Task creation failed"}

    cur.close()
    conn.close()

    return {
        "status": "accepted",
        "task_id": task_id,
        "tracking_id": tracking_id
    }
