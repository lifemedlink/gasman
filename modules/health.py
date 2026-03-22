from fastapi import Depends
from modules.jwt_auth import get_current_user
# modules/health.py
"""
Device Health Score
-------------------
Purpose:
- Compute a single HEALTH SCORE (0–100) per device
- Used in Admin / Subadmin dashboards

Health score considers:
1. Current gas percentage
2. Frequency of LOW / CRITICAL events (last 30 days)
3. Offline frequency
4. Recent refill success (task completion)

Score meaning:
90–100 → Excellent
70–89  → Good
40–69  → Warning
0–39   → Poor (needs attention)

Tables used:
- gasman_device_status
- gasman_history
- gasman_tasks
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from config.db_pool import get_gasman_db
from decimal import Decimal
from datetime import datetime, timedelta
import logging

router = APIRouter()
log = logging.getLogger("gasman.health")

# =====================================================
# HELPERS
# =====================================================

def get_user(user: dict = Depends(get_current_user)):
    u = None
    if not u:
        return None
    return {
        "name": u.get("name"),
        "role": (u.get("role") or "").lower()
    }

def fmt(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return v


# =====================================================
# HEALTH SCORE LOGIC
# =====================================================

def calculate_health_score(device, low_count, critical_count, offline_days, has_recent_refill):
    """
    Base score starts at 100, penalties applied.
    """

    score = 100

    # 🔥 Gas level penalty
    gas = device["gas_percentage"] or 0
    if gas < 20:
        score -= 30
    elif gas < 40:
        score -= 15

    # ⚠ LOW events
    score -= min(low_count * 3, 20)

    # 🚨 CRITICAL events
    score -= min(critical_count * 6, 30)

    # 📡 Offline penalty
    score -= min(offline_days * 4, 20)

    # ⛽ Bonus if recently refilled
    if has_recent_refill:
        score += 5

    return max(0, min(100, score))


# =====================================================
# API: DEVICE HEALTH (ADMIN / SUBADMIN)
# =====================================================

@router.get("/device_health")
def device_health(user: dict = Depends(get_current_user)):
    """
    Admin / Subadmin:
    Returns health score for ALL devices
    """

    user = get_user(request)
    if not user or user["role"] not in ("admin", "subadmin"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    since = datetime.utcnow() - timedelta(days=30)

    db = get_gasman_db()
    try:
        cur = db.cursor(dictionary=True)

        # 1️⃣ Current device status
        cur.execute("""
            SELECT
                device_id,
                gas_percentage,
                classification,
                online,
                updated_at
            FROM gasman_device_status
        """)
        devices = cur.fetchall()

        # 2️⃣ LOW / CRITICAL count (last 30 days)
        cur.execute("""
            SELECT
                device_id,
                SUM(classification='LOW') AS low_count,
                SUM(classification='CRITICAL') AS critical_count
            FROM gasman_history
            WHERE event_time >= %s
            GROUP BY device_id
        """, (since,))
        event_map = {
            r["device_id"]: r for r in cur.fetchall()
        }

        # 3️⃣ Offline days (rough)
        cur.execute("""
            SELECT
                device_id,
                COUNT(*) AS offline_days
            FROM gasman_history
            WHERE classification = 'CRITICAL'
              AND event_time >= %s
            GROUP BY device_id
        """, (since,))
        offline_map = {
            r["device_id"]: r["offline_days"] for r in cur.fetchall()
        }

        # 4️⃣ Recent refill success
        cur.execute("""
            SELECT DISTINCT device_id
            FROM gasman_tasks
            WHERE status = 'COMPLETED'
              AND completed_at >= %s
        """, (since,))
        refilled_devices = set(r["device_id"] for r in cur.fetchall())

        cur.close()

        result = []

        for d in devices:
            dev_id = d["device_id"]

            low_count = event_map.get(dev_id, {}).get("low_count", 0) or 0
            critical_count = event_map.get(dev_id, {}).get("critical_count", 0) or 0
            offline_days = offline_map.get(dev_id, 0)
            has_refill = dev_id in refilled_devices

            score = calculate_health_score(
                d, low_count, critical_count, offline_days, has_refill
            )

            status = (
                "EXCELLENT" if score >= 90 else
                "GOOD" if score >= 70 else
                "WARNING" if score >= 40 else
                "POOR"
            )

            result.append({
                "device_id": dev_id,
                "health_score": score,
                "health_status": status,
                "gas_percentage": fmt(d["gas_percentage"]),
                "classification": d["classification"],
                "online": bool(d["online"]),
                "low_events_30d": low_count,
                "critical_events_30d": critical_count,
                "recent_refill": has_refill
            })

        return JSONResponse(result)

    finally:
        try:
            db.close()
        except Exception:
            pass
