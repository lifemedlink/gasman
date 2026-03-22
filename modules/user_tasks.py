# modules/user_tasks.py
"""
GASMAN – USER TASK FSM (2 DATABASE VERSION)

✔ Uses data_logger for user_details
✔ Uses gasman DB for tasks
✔ Strict FSM
✔ One active task per driver
✔ Race-safe accept (FOR UPDATE)
✔ Auto GPS EN_ROUTE → ON_SITE (50m)
✔ Full endpoints restored
"""

from fastapi import APIRouter, Depends, HTTPException
from modules.jwt_auth import get_current_user
from modules.auth_dependency import require_login
from config.db_pool import get_data_logger_db, get_gasman_db
from datetime import datetime
import math

router = APIRouter(prefix="/user/task", tags=["User Tasks"])

ACTIVE_STATES = ("ASSIGNED", "EN_ROUTE", "ON_SITE", "FILLING", "FILLED")


# =========================================================
# HAVERSINE DISTANCE (METERS)
# =========================================================
def haversine_distance(lat1, lng1, lat2, lng2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi/2)**2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(dlambda/2)**2

    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# =========================================================
# DRIVER ROLE CHECK
# =========================================================
def assert_driver(user_name: str):
    conn = get_data_logger_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT role
        FROM user_details
        WHERE user_name = %s
        LIMIT 1
    """, (user_name,))

    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row or row["role"].lower() != "user":
        raise HTTPException(403, "Only drivers can perform task actions")


# =========================================================
# AUDIT LOG (ENTERPRISE VERSION)
# =========================================================
def log_activity(cur, task_id, device_id, user, action, status, note=None):

    cur.execute("""
        SELECT tracking_id
        FROM gasman_tasks
        WHERE id = %s
        LIMIT 1
    """, (task_id,))

    row = cur.fetchone()

    if not row or not row["tracking_id"]:
        return  # do not log before accept

    tracking_id = row["tracking_id"]

    cur.execute("""
        INSERT INTO gasman_task_activity
        (task_id, device_id, user_name, action, status_after, tracking_id, note)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (
        task_id,
        device_id,
        user,
        action,
        status,
        tracking_id,
        note
    ))

# =========================================================
# GET ACTIVE TASK (FULL FSM VERSION)
# =========================================================
@router.get("/active")
def get_active_task(
    user_payload: dict = Depends(get_current_user),
    _: dict = Depends(require_login),
    lat: float = None,
    lng: float = None
):
    username = user_payload["sub"]

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    # -----------------------------------------------------
    # 1️⃣ Get active task (include FILLING + FILLED)
    # -----------------------------------------------------
    cur.execute("""
        SELECT
    t.id AS task_id,
    t.device_id,
    t.status,
    t.tracking_id,

    t.initial_gas_level,
    t.accepted_at,
    t.en_route_at,
    t.on_site_at,
    t.completed_at,

    d.customer_name,
    g.device_location,
    g.coordinates,

    g.gas_percentage,
    g.classification

FROM gasman_tasks t

LEFT JOIN data_logger.device_log_current d
       ON d.device_id = t.device_id

LEFT JOIN gasman_device_status g
       ON g.device_id = t.device_id

WHERE t.accepted_by = %s
  AND t.status IN ('ASSIGNED','EN_ROUTE','ON_SITE','FILLING','FILLED')

ORDER BY t.id DESC
LIMIT 1
    """, (username,))

    task = cur.fetchone()

    if not task:
        cur.close()
        conn.close()
        return {}

    # =====================================================
    # 2️⃣ AUTO EN_ROUTE → ON_SITE (GPS DISTANCE)
    # =====================================================
    if (
        task["status"] == "EN_ROUTE"
        and lat is not None
        and lng is not None
        and task.get("coordinates")
    ):
        try:
            dev_lat, dev_lng = map(float, task["coordinates"].split(","))

            distance = haversine_distance(
                float(lat), float(lng),
                dev_lat, dev_lng
            )

            if distance <= 50:
                cur.execute("""
                    UPDATE gasman_tasks
                    SET status='ON_SITE',
                        on_site_at=NOW(),
                        onsite_source='AUTO',
                        updated_at=NOW()
                    WHERE id=%s
                """, (task["task_id"],))

                log_activity(
                    cur,
                    task["task_id"],
                    task["device_id"],
                    username,
                    "AUTO_ON_SITE",
                    "ON_SITE",
                    "Auto arrived (GPS ≤ 50m)"
                )

                conn.commit()
                task["status"] = "ON_SITE"

        except Exception as e:
            print("GPS promotion error:", e)

    # =====================================================
    # 3️⃣ ON_SITE → FILLING → FILLED (LIVE GAS FSM)
    # =====================================================
    try:
        cur.execute("""
            SELECT gas_percentage
            FROM gasman_device_status
            WHERE device_id = %s
        """, (task["device_id"],))

        gas_row = cur.fetchone()

        if gas_row:
            current_gas = float(gas_row["gas_percentage"])
            initial_gas = float(task.get("initial_gas_level") or 0)

            # --------------------------------------------
            # ON_SITE → FILLING
            # --------------------------------------------
            if task["status"] == "ON_SITE":

                # Store initial gas only once
                if initial_gas == 0:
                    cur.execute("""
                        UPDATE gasman_tasks
                        SET initial_gas_level=%s
                        WHERE id=%s
                    """, (current_gas, task["task_id"]))
                    conn.commit()
                    initial_gas = current_gas

                # Detect gas rising
                if current_gas > initial_gas + 2:
                    cur.execute("""
                        UPDATE gasman_tasks
                        SET status='FILLING',
                            updated_at=NOW()
                        WHERE id=%s
                    """, (task["task_id"],))

                    log_activity(
                        cur,
                        task["task_id"],
                        task["device_id"],
                        username,
                        "FILLING_STARTED",
                        "FILLING",
                        "Gas level increasing"
                    )

                    conn.commit()
                    task["status"] = "FILLING"

            # --------------------------------------------
            # FILLING → FILLED
            # --------------------------------------------
            if task["status"] == "FILLING":

                if current_gas >= 95:
                    cur.execute("""
                        UPDATE gasman_tasks
                        SET status='FILLED',
                            final_gas_level=%s,
                            updated_at=NOW()
                        WHERE id=%s
                    """, (current_gas, task["task_id"]))

                    log_activity(
                        cur,
                        task["task_id"],
                        task["device_id"],
                        username,
                        "GAS_FILLED",
                        "FILLED",
                        "Gas reached >= 95%"
                    )

                    conn.commit()
                    task["status"] = "FILLED"

    except Exception as e:
        print("Gas FSM error:", e)

    cur.close()
    conn.close()

    return task

# =========================================================
# GET PENDING TASK (DEVICE LOCK SAFE VERSION)
# =========================================================
@router.get("/pending")
def get_pending_task(
    user_payload: dict = Depends(get_current_user),
    _: dict = Depends(require_login),
    lat: float = None,
    lng: float = None
):
    username = user_payload["sub"]

    if lat is None or lng is None:
        return {}

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    # -----------------------------------------------------
    # Driver already has active task?
    # -----------------------------------------------------
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
        return {}

    # =====================================================
    # STEP 1 — NEAREST CRITICAL (DEVICE LOCK SAFE)
    # =====================================================
    cur.execute("""
        SELECT
            t.id AS task_id,
            t.device_id,
            d.customer_name,
            g.device_location,
            g.coordinates,
            g.gas_percentage,
            g.classification,
            (
                6371 * acos(
                    cos(radians(%s)) *
                    cos(radians(SUBSTRING_INDEX(g.coordinates, ',', 1))) *
                    cos(radians(SUBSTRING_INDEX(g.coordinates, ',', -1)) - radians(%s)) +
                    sin(radians(%s)) *
                    sin(radians(SUBSTRING_INDEX(g.coordinates, ',', 1)))
                )
            ) AS distance_km
        FROM gasman_tasks t
        JOIN data_logger.user_device_list ud
              ON ud.device_id = t.device_id
        JOIN data_logger.user_details u
              ON u.user_id = ud.user_id
        JOIN gasman_device_status g
              ON g.device_id = t.device_id
        JOIN data_logger.device_log_current d
              ON d.device_id = t.device_id
        WHERE u.user_name = %s
          AND t.status = 'PENDING'
          AND t.accepted_by IS NULL
          AND g.classification = 'CRITICAL'
          AND NOT EXISTS (
              SELECT 1
              FROM gasman_tasks t2
              WHERE t2.device_id = t.device_id
                AND t2.status IN ('ASSIGNED','EN_ROUTE','ON_SITE','FILLING','FILLED')
          )
        ORDER BY distance_km ASC
        LIMIT 1
    """, (lat, lng, lat, username))

    critical_task = cur.fetchone()

    if critical_task:
        cur.close()
        conn.close()
        return critical_task

    # =====================================================
    # STEP 2 — NEAREST LOW (ONLY IF NO CRITICAL)
    # =====================================================
    cur.execute("""
        SELECT
            t.id AS task_id,
            t.device_id,
            d.customer_name,
            g.device_location,
            g.coordinates,
            g.gas_percentage,
            g.classification,
            (
                6371 * acos(
                    cos(radians(%s)) *
                    cos(radians(SUBSTRING_INDEX(g.coordinates, ',', 1))) *
                    cos(radians(SUBSTRING_INDEX(g.coordinates, ',', -1)) - radians(%s)) +
                    sin(radians(%s)) *
                    sin(radians(SUBSTRING_INDEX(g.coordinates, ',', 1)))
                )
            ) AS distance_km
        FROM gasman_tasks t
        JOIN data_logger.user_device_list ud
              ON ud.device_id = t.device_id
        JOIN data_logger.user_details u
              ON u.user_id = ud.user_id
        JOIN gasman_device_status g
              ON g.device_id = t.device_id
        JOIN data_logger.device_log_current d
              ON d.device_id = t.device_id
        WHERE u.user_name = %s
          AND t.status = 'PENDING'
          AND t.accepted_by IS NULL
          AND g.classification = 'LOW'
          AND NOT EXISTS (
              SELECT 1
              FROM gasman_tasks t2
              WHERE t2.device_id = t.device_id
                AND t2.status IN ('ASSIGNED','EN_ROUTE','ON_SITE','FILLING','FILLED')
          )
        ORDER BY distance_km ASC
        LIMIT 1
    """, (lat, lng, lat, username))

    low_task = cur.fetchone()

    cur.close()
    conn.close()

    return low_task or {}

# =========================================================
# ACCEPT TASK (STABLE PRODUCTION VERSION)
# =========================================================
@router.post("/accept")
def accept_task(
    payload: dict,
    user_payload: dict = Depends(get_current_user),
    _: dict = Depends(require_login)
):
    username = user_payload["sub"]
    task_id = payload.get("task_id")

    if not task_id:
        raise HTTPException(400, "task_id required")

    assert_driver(username)

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    try:
        conn.start_transaction()

        # 1️⃣ Driver already has active task?
        cur.execute("""
            SELECT id
            FROM gasman_tasks
            WHERE accepted_by = %s
              AND status IN ('ASSIGNED','EN_ROUTE','ON_SITE','FILLING','FILLED')
            LIMIT 1
            FOR UPDATE
        """, (username,))

        if cur.fetchone():
            raise HTTPException(409, "Driver already has active task")

        # 2️⃣ Lock exact task
        cur.execute("""
            SELECT id, device_id
            FROM gasman_tasks
            WHERE id = %s
              AND status = 'PENDING'
              AND accepted_by IS NULL
            FOR UPDATE
        """, (task_id,))

        row = cur.fetchone()

        if not row:
            raise HTTPException(409, "Task already taken")

        device_id = row["device_id"]

        # 3️⃣ Generate tracking ID safely
        today = datetime.now().strftime("%Y%m%d")

        cur.execute("""
            INSERT INTO tracking_counters (dt, seq)
            VALUES (%s, 1)
            ON DUPLICATE KEY UPDATE seq = seq + 1
        """, (today,))

        cur.execute("SELECT seq FROM tracking_counters WHERE dt = %s", (today,))
        seq_row = cur.fetchone()

        if not seq_row:
            raise HTTPException(500, "Tracking counter error")

        seq = seq_row["seq"]
        tracking_id = f"GM-{today}-{seq:04d}"

        # 4️⃣ Assign task
        cur.execute("""
            UPDATE gasman_tasks
            SET accepted_by = %s,
                status = 'ASSIGNED',
                tracking_id = %s,
                accepted_at = NOW(),
                last_ping_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
        """, (username, tracking_id, task_id))

        # 5️⃣ Activity log (non-fatal)
        try:
            log_activity(
                cur,
                task_id,
                device_id,
                username,
                "ASSIGNED",
                "ASSIGNED",
                "Driver accepted task"
            )
        except Exception as log_err:
            print("Log insert failed:", log_err)

        conn.commit()

        return {
            "task_id": task_id,
            "device_id": device_id,
            "tracking_id": tracking_id,
            "status": "ASSIGNED"
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        print("ACCEPT ERROR:", str(e))
        raise HTTPException(500, f"Accept failed: {str(e)}")

    finally:
        cur.close()
        conn.close()
# =========================================================
# START TASK
# =========================================================
@router.post("/start")
def start_task(
    payload: dict,
    user_payload: dict = Depends(get_current_user),
    _: dict = Depends(require_login)
):
    username = user_payload["sub"]
    task_id = payload.get("task_id")

    if not task_id:
        raise HTTPException(400, "task_id required")

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        UPDATE gasman_tasks
        SET status='EN_ROUTE',
            en_route_at=NOW(),
            last_ping_at=NOW(),
            updated_at=NOW()
        WHERE id=%s
          AND accepted_by=%s
          AND status='ASSIGNED'
    """, (task_id, username))

    if cur.rowcount:

        cur.execute("SELECT device_id FROM gasman_tasks WHERE id=%s", (task_id,))
        row = cur.fetchone()

        log_activity(
            cur,
            task_id,
            row["device_id"],
            username,
            "NAVIGATION_STARTED",
            "EN_ROUTE",
            "Driver started navigation"
        )

    else:
        conn.commit()
        cur.close()
        conn.close()
        raise HTTPException(409, "Task not eligible for start")

    conn.commit()
    cur.close()
    conn.close()

    return {"ok": True}
# =========================================================
# MANUAL ON SITE
# =========================================================
@router.post("/on-site")
def arrive_task(
    payload: dict,
    user_payload: dict = Depends(get_current_user),
    _: dict = Depends(require_login)
):
    username = user_payload["sub"]
    task_id = payload.get("task_id")

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        UPDATE gasman_tasks
        SET status='ON_SITE',
            on_site_at=NOW(),
            onsite_source='MANUAL',
            updated_at=NOW()
        WHERE id=%s
          AND accepted_by=%s
          AND status='EN_ROUTE'
    """, (task_id, username))

    if cur.rowcount:

        cur.execute("SELECT device_id FROM gasman_tasks WHERE id=%s", (task_id,))
        row = cur.fetchone()

        log_activity(
            cur,
            task_id,
            row["device_id"],
            username,
            "MANUAL_ON_SITE",
            "ON_SITE",
            "Driver confirmed arrival"
        )

    conn.commit()
    cur.close()
    conn.close()

    return {"ok": True}


# =========================================================
# REJECT TASK
# =========================================================
@router.post("/reject")
def reject_task(
    payload: dict,
    user_payload: dict = Depends(get_current_user),
    _: dict = Depends(require_login)
):
    device_id = payload.get("device_id")

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        UPDATE gasman_tasks
        SET status='REJECTED',
            updated_at=NOW()
        WHERE device_id=%s
          AND status='PENDING'
        ORDER BY created_at DESC
        LIMIT 1
    """, (device_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"ok": True}

# =========================================================
# CANCEL TASK
# =========================================================
@router.post("/cancel")
def cancel_task(
    payload: dict,
    user_payload: dict = Depends(get_current_user),
    _: dict = Depends(require_login)
):
    username = user_payload["sub"]
    task_id = payload.get("task_id")

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        UPDATE gasman_tasks
        SET status='CANCELLED',
            updated_at=NOW()
        WHERE id=%s
          AND accepted_by=%s
          AND status IN ('ASSIGNED','EN_ROUTE','ON_SITE','FILLING','FILLED')
    """, (task_id, username))

    if cur.rowcount:

        cur.execute("SELECT device_id FROM gasman_tasks WHERE id=%s", (task_id,))
        row = cur.fetchone()

        log_activity(
            cur,
            task_id,
            row["device_id"],
            username,
            "CANCELLED",
            "CANCELLED",
            "Driver cancelled task"
        )

    conn.commit()
    cur.close()
    conn.close()

    return {"ok": True}

# =========================================================
# COMPLETE TASK
# =========================================================
@router.post("/complete")
def complete_task(
    payload: dict,
    user_payload: dict = Depends(get_current_user),
    _: dict = Depends(require_login)
):
    username = user_payload["sub"]
    task_id = payload.get("task_id")

    if not task_id:
        raise HTTPException(400, "task_id required")

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    # Get device id
    cur.execute("""
        SELECT device_id
        FROM gasman_tasks
        WHERE id=%s
          AND accepted_by=%s
          AND status IN ('ON_SITE','FILLING','FILLED')
    """, (task_id, username))

    row = cur.fetchone()

    if not row:
        conn.commit()
        cur.close()
        conn.close()
        raise HTTPException(409, "Task not eligible for completion")

    device_id = row["device_id"]

    # Get current gas %
    cur.execute("""
        SELECT gas_percentage
        FROM gasman_device_status
        WHERE device_id=%s
    """, (device_id,))

    gas_row = cur.fetchone()
    final_gas = gas_row["gas_percentage"] if gas_row else None

    # Complete task
    cur.execute("""
        UPDATE gasman_tasks
        SET status='COMPLETED',
            final_gas_level=%s,
            completed_at=NOW(),
            updated_at=NOW()
        WHERE id=%s
    """, (final_gas, task_id))

    log_activity(
        cur,
        task_id,
        device_id,
        username,
        "TASK_COMPLETED",
        "COMPLETED",
        "Driver manually completed task"
    )

    conn.commit()
    cur.close()
    conn.close()

    return {"ok": True}
# =========================================================
# LAST COMPLETED
# =========================================================
@router.get("/last-completed")
def last_completed(
    user_payload: dict = Depends(get_current_user),
    _: dict = Depends(require_login)
):
    username = user_payload["sub"]

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT id AS task_id, onsite_source
        FROM gasman_tasks
        WHERE accepted_by=%s
          AND status='COMPLETED'
          AND completed_at >= NOW() - INTERVAL 15 SECOND
        ORDER BY completed_at DESC
        LIMIT 1
    """, (username,))

    row = cur.fetchone()
    cur.close()
    conn.close()

    return row or {}


# =========================================================
# COMPLETED BY ID
# =========================================================
@router.get("/completed/{task_id}")
def completed_task(
    task_id: int,
    user_payload: dict = Depends(get_current_user),
    _: dict = Depends(require_login)
):
    username = user_payload["sub"]

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT id, onsite_source
        FROM gasman_tasks
        WHERE id=%s
          AND accepted_by=%s
          AND status='COMPLETED'
    """, (task_id, username))

    row = cur.fetchone()
    cur.close()
    conn.close()

    return row or {}
# =========================================================
# GPS PING (AUTO EN_ROUTE → ON_SITE)
# =========================================================
@router.post("/gps-ping")
def gps_ping(
    payload: dict,
    user_payload: dict = Depends(get_current_user),
    _: dict = Depends(require_login)
):
    username = user_payload["sub"]
    lat = payload.get("lat")
    lng = payload.get("lng")

    if lat is None or lng is None:
        raise HTTPException(400, "lat and lng required")

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    # Save location history
    cur.execute("""
        INSERT INTO gasman_user_location_history
        (user_name, lat, lng)
        VALUES (%s,%s,%s)
    """, (username, lat, lng))

    # Get active EN_ROUTE task
    cur.execute("""
        SELECT t.id, g.coordinates
        FROM gasman_tasks t
        JOIN gasman_device_status g
             ON g.device_id = t.device_id
        WHERE t.accepted_by=%s
          AND t.status='EN_ROUTE'
        LIMIT 1
    """, (username,))

    task = cur.fetchone()

    if not task:
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True}

    if not task["coordinates"]:
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True}

    device_lat, device_lng = map(float, task["coordinates"].split(","))

    distance = haversine_distance(
        float(lat), float(lng),
        device_lat, device_lng
    )

    # 100 meters threshold
    if distance <= 100:

        cur.execute("""
            UPDATE gasman_tasks
            SET status='ON_SITE',
                on_site_at=NOW(),
                onsite_source='AUTO',
                updated_at=NOW()
            WHERE id=%s
              AND status='EN_ROUTE'
        """, (task["id"],))

        if cur.rowcount:

            log_activity(
                cur,
                task["id"],
                None,
                username,
                "AUTO_ON_SITE",
                "ON_SITE",
                "Auto arrival via GPS"
            )

    conn.commit()
    cur.close()
    conn.close()

    return {"ok": True}
