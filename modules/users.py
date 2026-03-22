from fastapi import Depends
from modules.jwt_auth import get_current_user
# modules/users.py
"""
GASMAN – USER PERFORMANCE & RANKING (UPDATED)

✔ Admin / Subadmin leaderboard
✔ User self performance
✔ JSON-safe (Decimal + datetime safe)
✔ Production safe DB closing
✔ Clean scoring logic
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from config.db_pool import get_gasman_db
from datetime import datetime, timedelta
from decimal import Decimal
import logging

router = APIRouter()
log = logging.getLogger("gasman.users")


# =====================================================
# SESSION HELPER
# =====================================================

def get_user(user: dict = Depends(get_current_user)):
    user = None
    if not user:
        return None
    return {
        "name": user.get("name"),
        "role": (user.get("role") or "").lower()
    }


# =====================================================
# SAFE JSON FORMATTER
# =====================================================

def fmt(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


# =====================================================
# PERFORMANCE SCORE ENGINE
# =====================================================

def calculate_user_score(
    completed,
    cancelled,
    avg_accept_sec,
    avg_complete_sec
):
    """
    Score starts at 100
    Penalties reduce it
    Bonus increases it
    """

    score = 100

    # Cancel penalty
    score -= (cancelled or 0) * 5

    # Slow acceptance penalty (>10 min)
    if avg_accept_sec and avg_accept_sec > 600:
        score -= min(((avg_accept_sec - 600) / 60) * 2, 20)

    # Slow completion penalty (>60 min)
    if avg_complete_sec and avg_complete_sec > 3600:
        score -= min(((avg_complete_sec - 3600) / 300) * 2, 30)

    # Completion bonus
    score += min((completed or 0) * 1.5, 15)

    return max(0, min(100, int(score)))


# =====================================================
# ADMIN: USER PERFORMANCE (LEADERBOARD)
# =====================================================

@router.get("/users/performance")
def user_performance(user: dict = Depends(get_current_user), days: int = 30):

    user = get_user(request)
    if not user or user["role"] not in ("admin", "subadmin"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    since = datetime.utcnow() - timedelta(days=days)

    db = get_gasman_db()
    try:
        cur = db.cursor(dictionary=True)

        # TASK SUMMARY
        cur.execute("""
            SELECT
                user_name,
                COUNT(*) AS total_tasks,
                SUM(status = 'COMPLETED') AS completed,
                SUM(status = 'CANCELLED') AS cancelled
            FROM gasman_tasks
            WHERE created_at >= %s
            GROUP BY user_name
        """, (since,))
        task_stats = {
            r["user_name"]: r for r in cur.fetchall()
        }

        # SLA SUMMARY
        cur.execute("""
            SELECT
                user_name,
                AVG(TIMESTAMPDIFF(SECOND, created_at, accepted_at)) AS avg_accept_sec,
                AVG(TIMESTAMPDIFF(SECOND, accepted_at, completed_at)) AS avg_complete_sec
            FROM gasman_tasks
            WHERE created_at >= %s
              AND status = 'COMPLETED'
              AND accepted_at IS NOT NULL
              AND completed_at IS NOT NULL
            GROUP BY user_name
        """, (since,))
        sla_stats = {
            r["user_name"]: r for r in cur.fetchall()
        }

        cur.close()

        results = []

        for username, task in task_stats.items():

            sla = sla_stats.get(username, {})

            completed = task.get("completed") or 0
            cancelled = task.get("cancelled") or 0

            avg_accept = sla.get("avg_accept_sec")
            avg_complete = sla.get("avg_complete_sec")

            score = calculate_user_score(
                completed,
                cancelled,
                avg_accept,
                avg_complete
            )

            grade = (
                "A" if score >= 90 else
                "B" if score >= 75 else
                "C" if score >= 60 else
                "D"
            )

            results.append({
                "user_name": username,
                "performance_score": score,
                "grade": grade,
                "tasks_completed": completed,
                "tasks_cancelled": cancelled,
                "avg_accept_time_sec": fmt(avg_accept),
                "avg_completion_time_sec": fmt(avg_complete)
            })

        # RANKING
        results.sort(key=lambda x: x["performance_score"], reverse=True)

        for index, row in enumerate(results, start=1):
            row["rank"] = index

        return JSONResponse(results)

    finally:
        try:
            db.close()
        except Exception:
            pass


# =====================================================
# USER: SELF PERFORMANCE
# =====================================================

@router.get("/users/me")
def my_performance(user: dict = Depends(get_current_user), days: int = 30):

    user = get_user(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    username = user["name"]
    since = datetime.utcnow() - timedelta(days=days)

    db = get_gasman_db()
    try:
        cur = db.cursor(dictionary=True)

        cur.execute("""
            SELECT
                COUNT(*) AS total_tasks,
                SUM(status = 'COMPLETED') AS completed,
                SUM(status = 'CANCELLED') AS cancelled,
                AVG(TIMESTAMPDIFF(SECOND, created_at, accepted_at)) AS avg_accept_sec,
                AVG(TIMESTAMPDIFF(SECOND, accepted_at, completed_at)) AS avg_complete_sec
            FROM gasman_tasks
            WHERE user_name = %s
              AND created_at >= %s
        """, (username, since))

        result = cur.fetchone() or {}
        cur.close()

        score = calculate_user_score(
            result.get("completed") or 0,
            result.get("cancelled") or 0,
            result.get("avg_accept_sec"),
            result.get("avg_complete_sec")
        )

        return JSONResponse({
            "user_name": username,
            "performance_score": score,
            "tasks_completed": result.get("completed") or 0,
            "tasks_cancelled": result.get("cancelled") or 0,
            "avg_accept_time_sec": fmt(result.get("avg_accept_sec")),
            "avg_completion_time_sec": fmt(result.get("avg_complete_sec"))
        })

    finally:
        try:
            db.close()
        except Exception:
            pass
