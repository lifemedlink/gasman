# modules/fast_cache.py
"""
Fast Cache Layer (Redis) – GASMAN
---------------------------------
✔ Redis-first read
✔ Dual DB support (data_logger + gasman)
✔ Safe fallback
✔ Driver filtering
✔ Production safe
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from config.redis_client import redis_client
from config.db_pool import get_data_logger_db, get_gasman_db
from modules.jwt_auth import get_current_user
from decimal import Decimal
from datetime import datetime
from fastapi.encoders import jsonable_encoder
import json
import logging

router = APIRouter()
log = logging.getLogger("gasman.fast_cache")

REDIS_KEY = "gasman:devices:latest"
REDIS_TTL = 5  # seconds


# =====================================================
# HELPERS
# =====================================================

def fmt(row):
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
# CORE DB FETCH (SOURCE OF TRUTH)
# =====================================================

def fetch_from_db():
    """
    Pull:
    - device list from data_logger
    - device status + tasks from gasman
    """

    dl_conn = get_data_logger_db()
    gm_conn = get_gasman_db()

    try:
        # -------------------------------
        # DEVICE BASE (data_logger)
        # -------------------------------
        dl_cur = dl_conn.cursor(dictionary=True)
        dl_cur.execute("""
            SELECT device_id, coordinates
            FROM device_log_current
            ORDER BY device_id
        """)
        devices = dl_cur.fetchall()
        dl_cur.close()

        # -------------------------------
        # DEVICE STATUS (gasman)
        # -------------------------------
        gm_cur = gm_conn.cursor(dictionary=True)
        gm_cur.execute("""
            SELECT
                device_id,
                gas_percentage,
                classification,
                online
            FROM gasman_device_status
        """)
        status_rows = gm_cur.fetchall()

        status_map = {r["device_id"]: r for r in status_rows}

        # -------------------------------
        # ACTIVE TASKS (gasman)
        # -------------------------------
        gm_cur.execute("""
            SELECT device_id, user_name, status, tracking_id
            FROM gasman_tasks
            WHERE status IN ('PENDING','ASSIGNED','EN_ROUTE','ON_SITE')
            ORDER BY updated_at DESC
        """)
        task_rows = gm_cur.fetchall()
        gm_cur.close()

        task_map = {}
        for t in task_rows:
            if t["device_id"] not in task_map:
                task_map[t["device_id"]] = t

        critical, low, normal, offline = [], [], [], []

        for r in devices:
            d = fmt(r)

            status = status_map.get(d["device_id"])
            task = task_map.get(d["device_id"])

            d["gas_percentage"] = 0
            d["classification"] = "NORMAL"
            d["online"] = 0
            d["assigned_users"] = []
            d["task_status"] = None
            d["tracking_id"] = None

            if status:
                d["gas_percentage"] = float(status["gas_percentage"] or 0)
                d["classification"] = status["classification"] or "NORMAL"
                d["online"] = status["online"]

            if task:
                d["assigned_users"] = [task["user_name"]]
                d["task_status"] = task["status"]
                d["tracking_id"] = task["tracking_id"]

            if not d["online"]:
                offline.append(d)
                continue

            cls = d["classification"].upper()
            if cls == "CRITICAL":
                critical.append(d)
            elif cls == "LOW":
                low.append(d)
            else:
                normal.append(d)

        return {
            "critical": critical,
            "low": low,
            "normal": normal,
            "offline": offline
        }

    finally:
        dl_conn.close()
        gm_conn.close()


# =====================================================
# FAST CACHE ENDPOINT
# =====================================================

@router.get("/fast/get_locations")
def fast_get_locations(user: dict = Depends(get_current_user)):

    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    role = (user.get("role") or "").lower()
    username = user.get("sub")

    # -------------------------
    # 1️⃣ Try Redis
    # -------------------------
    try:
        cached = redis_client.get(REDIS_KEY)
        if cached:
            data = json.loads(cached)
            log.debug("FAST CACHE HIT")

            if role == "user":
                data = filter_for_user(data, username)

            return JSONResponse(data)
    except Exception:
        log.warning("Redis unavailable, fallback to DB")

    # -------------------------
    # 2️⃣ Fallback to DB
    # -------------------------
    data = fetch_from_db()

    # -------------------------
    # 3️⃣ Save to Redis
    # -------------------------
    try:
        safe_data = jsonable_encoder(
            data,
            custom_encoder={Decimal: float}
        )
        redis_client.setex(
            REDIS_KEY,
            REDIS_TTL,
            json.dumps(safe_data)
        )
    except Exception:
        pass

    if role == "user":
        data = filter_for_user(data, username)

    return JSONResponse(data)


# =====================================================
# USER FILTER
# =====================================================

def filter_for_user(data, username):
    """
    Drivers see:
    - Their assigned devices
    - OR unassigned CRITICAL/LOW
    """

    def allow(d):
        if not d.get("assigned_users"):
            return True
        return username in d["assigned_users"]

    return {
        "critical": [d for d in data["critical"] if allow(d)],
        "low": [d for d in data["low"] if allow(d)],
        "normal": [],
        "offline": []
    }
