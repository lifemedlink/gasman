# modules/devices.py
"""
GASMAN – ADMIN DEVICES API (PRODUCTION FINAL)
---------------------------------------------
✔ ADMIN ONLY
✔ DB = source of truth
✔ NO user logic
✔ NO task logic
✔ NO Redis dependency
✔ Safe for dashboards & tables
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from config.db_pool import get_gasman_db
from fastapi import Depends
from modules.jwt_auth import get_current_user
from modules.auth_dependency import require_admin
from datetime import datetime
from decimal import Decimal

router = APIRouter()

# ======================================================
# JSON SAFE CONVERTER
# ======================================================
def json_safe(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, datetime):
            out[k] = v.strftime("%Y-%m-%d %H:%M:%S")
        else:
            out[k] = v
    return out


# ======================================================
# INTERNAL: ADMIN MAP DEVICES
# Used by admin_map ONLY
# ======================================================
def get_admin_map_devices():
    db = db = get_gasman_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT
            device_id,
            coordinates,
            gas_percentage,
            classification,
            system_status,
            last_log_time,
            online
        FROM gasman_device_status
        WHERE coordinates IS NOT NULL
    """)

    rows = cur.fetchall()
    cur.close()
    db.close()

    result = []
    for r in rows:
        r = json_safe(r)
        result.append({
            "device_id": r["device_id"],
            "coordinates": r["coordinates"],
            "gas_percent": r["gas_percentage"],
            "classification": r["classification"],
            "system_status": r["system_status"],
            "offline": not bool(r["online"]),
            "last_update": r["last_log_time"]
        })

    return result


# ======================================================
# ADMIN DEVICE LIST (TABLE VIEW)
# ======================================================
@router.get("/devices/list")
def devices_list(
    request: Request,
    _: dict = Depends(require_admin)
):
    db = db = get_gasman_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT
            g.device_id,
            d.customer_name,
            g.device_location,

            g.online,
            g.system_status,
            g.gas_alarm_status,
            g.operation_status,
            g.classification,

            g.gas_leak_percent,
            g.gas_percentage,
            g.tank_pressure_bar,
            g.line_pressure_bar,

            g.tank_level_flag,
            g.line_pressure_flag,
            g.gas_leak_flag,
            g.power_fault,
            g.device_offline,

            g.last_log_time
        FROM gasman_device_status g
        LEFT JOIN data_logger.devicelist d ON d.device_id = g.device_id
        ORDER BY d.customer_name, g.device_id
    """)

    rows = cur.fetchall()
    cur.close()
    db.close()

    response = []

    for r in rows:
        r = json_safe(r)

        if r["last_log_time"]:
            state = "Online" if r["online"] else "Offline"
            last_update_text = f"{state} · {r['last_log_time']}"
        else:
            last_update_text = "No data"

        response.append({
            "device_id": r["device_id"],
            "customer_name": r.get("customer_name") or "-",
            "location": r.get("device_location") or "-",

            "online": bool(r["online"]),
            "system_status": r["system_status"],
            "gas_alarm_status": r["gas_alarm_status"],
            "operation_status": r["operation_status"],
            "classification": r["classification"],

            "gas_leak_percent": r["gas_leak_percent"],
            "tank_level_percent": r["gas_percentage"],
            "tank_pressure": r["tank_pressure_bar"],
            "line_pressure": r["line_pressure_bar"],

            "tank_level_flag": r["tank_level_flag"],
            "line_pressure_flag": r["line_pressure_flag"],
            "gas_leak_flag": r["gas_leak_flag"],
            "power_fault": bool(r["power_fault"]),
            "device_offline": bool(r["device_offline"]),

            "last_update_text": last_update_text
        })

    return JSONResponse(response)


# ======================================================
# ADMIN KPI COUNTS
# ======================================================
@router.get("/devices")
def devices_kpi(_: dict = Depends(require_admin)):

    db = get_gasman_db()
    cur = db.cursor(dictionary=True)

    # DEVICE COUNTS
    cur.execute("""
        SELECT
            COUNT(*) as total_devices,
            SUM(classification = 'CRITICAL') as critical,
            SUM(classification = 'LOW') as low,
            SUM(classification = 'NORMAL') as normal,
            SUM(online = 0) as offline,
            SUM(online = 1) as online
        FROM gasman_device_status
    """)

    device_counts = cur.fetchone()

    # ACTIVE TASK COUNT
    cur.execute("""
        SELECT COUNT(*) as active_tasks
        FROM gasman_tasks
        WHERE status IN ('ASSIGNED','EN_ROUTE','ON_SITE','FILLING')
    """)

    task_count = cur.fetchone()

    cur.close()
    db.close()

    return {
        "total_devices": device_counts["total_devices"] or 0,
        "critical": device_counts["critical"] or 0,
        "low": device_counts["low"] or 0,
        "normal": device_counts["normal"] or 0,
        "offline": device_counts["offline"] or 0,
        "online": device_counts["online"] or 0,
        "active_tasks": task_count["active_tasks"] or 0
    }
