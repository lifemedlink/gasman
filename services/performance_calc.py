# services/performance_calc.py
"""
PERFORMANCE CALCULATION ENGINE – GASMAN
--------------------------------------
Calculates DRIVER PERFORMANCE SCORE (0–100)

NO DB WRITES
READ-ONLY
SAFE for shared data_logger database
"""

from datetime import datetime, timedelta
from config.db_pool import get_gasman_db

# ===============================
# WEIGHTS (FINAL – TUNABLE)
# ===============================
WEIGHTS = {
    "task_completion": 40,
    "sla_compliance": 30,
    "response_speed": 20,
    "consistency": 10
}

SLA_TARGETS = {
    "low_to_accept_minutes": 15,
    "accept_to_complete_minutes": 45
}


# ===============================
# HELPERS
# ===============================
def _minutes(a, b):
    return (b - a).total_seconds() / 60


def _safe_pct(val):
    return max(0, min(100, round(float(val), 2)))


# ===============================
# CORE USER SCORE
# ===============================
def get_user_performance(user_name: str, days: int = 30) -> dict:
    """
    Calculate performance score for a single driver
    """
    db = get_gasman_db()
    cur = None

    try:
        cur = db.cursor(dictionary=True)
        since = datetime.utcnow() - timedelta(days=days)

        # ---------------------------
        # TASK SUMMARY
        # ---------------------------
        cur.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(status='COMPLETED') AS completed,
                SUM(status='CANCELLED') AS cancelled
            FROM gasman_tasks
            WHERE user_name = %s
              AND created_at >= %s
        """, (user_name, since))

        t = cur.fetchone() or {}
        total = int(t.get("total") or 0)
        completed = int(t.get("completed") or 0)
        cancelled = int(t.get("cancelled") or 0)

        if total == 0:
            return {
                "user": user_name,
                "period_days": days,
                "score": 0,
                "reason": "no_tasks"
            }

        completion_rate = (completed / total) * 100.0

        # ---------------------------
        # SLA COMPLIANCE
        # ---------------------------
        cur.execute("""
            SELECT accepted_at, created_at
            FROM gasman_tasks
            WHERE user_name = %s
              AND status = 'COMPLETED'
              AND created_at >= %s
        """, (user_name, since))

        rows = cur.fetchall() or []

        sla_ok = 0
        response_times = []

        for r in rows:
            if r["accepted_at"] and r["created_at"]:
                low_to_accept = _minutes(
                    r["created_at"],
                    r["accepted_at"]
                )
                response_times.append(float(low_to_accept))

                if low_to_accept <= SLA_TARGETS["low_to_accept_minutes"]:
                    sla_ok += 1

        sla_rate = (sla_ok / len(rows) * 100.0) if rows else 0.0

        avg_response = (
            sum(response_times) / len(response_times)
            if response_times else None
        )

        # ---------------------------
        # CONSISTENCY
        # ---------------------------
        cur.execute("""
            SELECT COUNT(DISTINCT DATE(created_at)) AS active_days
            FROM gasman_tasks
            WHERE user_name = %s
              AND created_at >= %s
        """, (user_name, since))

        active_days = int((cur.fetchone() or {}).get("active_days") or 0)
        consistency_rate = min(100.0, (active_days / days) * 100.0)

        # ---------------------------
        # SCORE CALCULATION (FLOAT SAFE)
        # ---------------------------
        response_component = 0.0

        if avg_response is not None:
            response_component = (
                max(0.0, 100.0 - float(avg_response))
                * float(WEIGHTS["response_speed"])
                / 100.0
            )

        score = (
            completion_rate * float(WEIGHTS["task_completion"]) / 100.0 +
            sla_rate * float(WEIGHTS["sla_compliance"]) / 100.0 +
            response_component +
            consistency_rate * float(WEIGHTS["consistency"]) / 100.0
        )

        return {
            "user": user_name,
            "period_days": days,
            "score": _safe_pct(score),
            "details": {
                "tasks_total": total,
                "completed": completed,
                "cancelled": cancelled,
                "completion_rate_pct": round(completion_rate, 2),
                "sla_compliance_pct": round(sla_rate, 2),
                "avg_response_min": round(avg_response, 2) if avg_response else None,
                "consistency_pct": round(consistency_rate, 2)
            }
        }

    finally:
        try:
            if cur:
                cur.close()
            db.close()
        except Exception:
            pass


# ===============================
# RANKING (ADMIN)
# ===============================
def get_driver_ranking(days: int = 30, limit: int = 20):
    """
    Rank drivers by performance score
    """
    db = get_gasman_db()
    cur = None

    try:
        cur = db.cursor()

        cur.execute("""
            SELECT DISTINCT user_name
            FROM gasman_tasks
            WHERE created_at >= NOW() - INTERVAL %s DAY
        """, (days,))

        users = [r[0] for r in cur.fetchall()]

        scores = []
        for u in users:
            p = get_user_performance(u, days)
            if isinstance(p, dict) and "score" in p:
                scores.append(p)

        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:limit]

    finally:
        try:
            if cur:
                cur.close()
            db.close()
        except Exception:
            pass
