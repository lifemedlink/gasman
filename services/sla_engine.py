# services/sla_engine.py
"""
SLA ENGINE – GASMAN (FINAL, DB-ALIGNED)
-------------------------------------
✔ Uses gasman_tasks ONLY
✔ No gasman_history dependency
✔ No N+1 queries
✔ Fast & correct
✔ Dashboard safe
"""

from datetime import datetime
from config.db_pool import get_gasman_db


# =========================
# SLA CONFIG (TUNABLE)
# =========================
SLA_LIMITS = {
    "low_to_accept_minutes": 15,
    "accept_to_complete_minutes": 45
}


# =========================
# HELPERS
# =========================
def _minutes(a, b):
    return round((b - a).total_seconds() / 60, 2)


def _safe_dt(v):
    return v if isinstance(v, datetime) else None


# =========================
# SINGLE TASK SLA
# =========================
def get_sla_for_task(task_id: int) -> dict:
    """
    Calculate SLA for a single task (DB-driven)
    """
    db = get_gasman_db()
    cur = db.cursor(dictionary=True)

    try:
        cur.execute("""
            SELECT
                id,
                device_id,
                user_name,
                status,
                created_at,
                accepted_at,
                completed_at
            FROM gasman_tasks
            WHERE id = %s
        """, (task_id,))
        t = cur.fetchone()

        if not t:
            return {"error": "task_not_found"}

        t_low = _safe_dt(t["created_at"])
        t_accept = _safe_dt(t["accepted_at"])
        t_complete = _safe_dt(t["completed_at"])

        sla = {
            "task_id": task_id,
            "device_id": t["device_id"],
            "user_name": t["user_name"],
            "status": t["status"]
        }

        # LOW → ACCEPT
        if t_low and t_accept:
            sla["low_to_accept_min"] = _minutes(t_low, t_accept)
            sla["low_to_accept_ok"] = (
                sla["low_to_accept_min"] <= SLA_LIMITS["low_to_accept_minutes"]
            )
        else:
            sla["low_to_accept_min"] = None
            sla["low_to_accept_ok"] = False

        # ACCEPT → COMPLETE
        if t_accept and t_complete:
            sla["accept_to_complete_min"] = _minutes(t_accept, t_complete)
            sla["accept_to_complete_ok"] = (
                sla["accept_to_complete_min"] <= SLA_LIMITS["accept_to_complete_minutes"]
            )
        else:
            sla["accept_to_complete_min"] = None
            sla["accept_to_complete_ok"] = False

        # TOTAL
        if t_low and t_complete:
            sla["total_resolution_min"] = _minutes(t_low, t_complete)
        else:
            sla["total_resolution_min"] = None

        return sla

    finally:
        cur.close()
        db.close()


# =========================
# DASHBOARD SUMMARY (FAST)
# =========================
def get_sla_summary(days: int = 7) -> dict:
    """
    SLA summary for admin dashboard (single query)
    """
    db = get_gasman_db()
    cur = db.cursor(dictionary=True)

    try:
        cur.execute("""
            SELECT
                created_at,
                accepted_at,
                completed_at
            FROM gasman_tasks
            WHERE created_at >= NOW() - INTERVAL %s DAY
              AND status = 'COMPLETED'
        """, (days,))
        rows = cur.fetchall()

        if not rows:
            return {
                "period_days": days,
                "tasks_completed": 0,
                "low_to_accept_sla_pct": 0,
                "accept_to_complete_sla_pct": 0
            }

        ok_accept = 0
        ok_complete = 0
        total = len(rows)

        for r in rows:
            if r["accepted_at"]:
                if _minutes(r["created_at"], r["accepted_at"]) <= SLA_LIMITS["low_to_accept_minutes"]:
                    ok_accept += 1

            if r["accepted_at"] and r["completed_at"]:
                if _minutes(r["accepted_at"], r["completed_at"]) <= SLA_LIMITS["accept_to_complete_minutes"]:
                    ok_complete += 1

        return {
            "period_days": days,
            "tasks_completed": total,
            "low_to_accept_sla_pct": round(ok_accept / total * 100, 2),
            "accept_to_complete_sla_pct": round(ok_complete / total * 100, 2)
        }

    finally:
        cur.close()
        db.close()
