# modules/activity.py
"""
GASMAN – ADMIN ACTIVITY (FSM SAFE VERSION)
-------------------------------------------
✔ Correct latest status per tracking_id
✔ Uses ROW_NUMBER() instead of MAX(status)
✔ Uses gasman DB for task activity
✔ Uses data_logger DB for devicelist
✔ No cross-DB joins
✔ Clean JSON output
✔ JWT protected
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from config.db_pool import get_gasman_db, get_data_logger_db
from modules.auth_dependency import require_admin
from decimal import Decimal
from datetime import datetime
import logging

router = APIRouter()
log = logging.getLogger("gasman.activity")


# =========================================================
# SAFE FORMATTER
# =========================================================
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


# =========================================================
# ADMIN ACTIVITY
# =========================================================
@router.get("/get_activity")
def get_activity(
    _: dict = Depends(require_admin),
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = Query(200, le=1000)
):
    """
    Returns:
    {
      summary: [],
      timeline: []
    }
    """

    gasman_db = get_gasman_db()
    gcur = gasman_db.cursor(dictionary=True)

    try:

        # =====================================================
        # SUMMARY (CORRECT LATEST STATUS PER TRACKING ID)
        # =====================================================
        summary_sql = """
        SELECT
            x.tracking_id,
            x.device_id,
            x.user_name,
            x.status_after AS status,
            x.created_at,
            t.initial_gas_level AS gas_start,
            t.final_gas_level AS gas_end
        FROM (
            SELECT
                a.*,
                ROW_NUMBER() OVER (
                    PARTITION BY a.tracking_id
                    ORDER BY a.created_at DESC
                ) rn
            FROM gasman_task_activity a
            WHERE a.tracking_id IS NOT NULL
        """

        params = []

        if start_date:
            summary_sql += " AND a.created_at >= %s"
            params.append(start_date + " 00:00:00")

        if end_date:
            summary_sql += " AND a.created_at <= %s"
            params.append(end_date + " 23:59:59")

        summary_sql += """
        ) x
        LEFT JOIN gasman_tasks t
               ON t.id = x.task_id
        WHERE x.rn = 1
        ORDER BY x.created_at DESC
        LIMIT %s
        """

        params.append(limit)

        gcur.execute(summary_sql, params)
        summary = gcur.fetchall()

        # =====================================================
        # TIMELINE (FULL AUDIT LOG)
        # =====================================================
        timeline_sql = """
        SELECT
            tracking_id,
            device_id,
            user_name,
            action,
            status_after,
            note,
            created_at
        FROM gasman_task_activity
        WHERE tracking_id IS NOT NULL
        """

        t_params = []

        if start_date:
            timeline_sql += " AND created_at >= %s"
            t_params.append(start_date + " 00:00:00")

        if end_date:
            timeline_sql += " AND created_at <= %s"
            t_params.append(end_date + " 23:59:59")

        timeline_sql += " ORDER BY created_at ASC"

        gcur.execute(timeline_sql, t_params)
        timeline = gcur.fetchall()

        # =====================================================
        # ENRICH DEVICE INFO (FROM data_logger DB)
        # =====================================================
        device_ids = list(
            {row["device_id"] for row in summary if row["device_id"]}
        )

        device_map = {}

        if device_ids:
            dl_db = get_data_logger_db()
            dl_cur = dl_db.cursor(dictionary=True)

            placeholders = ",".join(["%s"] * len(device_ids))

            dl_cur.execute(
                f"""
                SELECT device_id, customer_name, address
                FROM devicelist
                WHERE device_id IN ({placeholders})
                """,
                device_ids
            )

            for d in dl_cur.fetchall():
                device_map[d["device_id"]] = {
                    "customer_name": d["customer_name"],
                    "location": d["address"]
                }

            dl_cur.close()
            dl_db.close()

        # attach device info to summary
        for row in summary:
            info = device_map.get(row["device_id"])
            if info:
                row["customer_name"] = info["customer_name"]
                row["location"] = info["location"]

        # attach device info to timeline
        for row in timeline:
            info = device_map.get(row["device_id"])
            if info:
                row["customer_name"] = info["customer_name"]
                row["location"] = info["location"]

        return {
            "summary": [fmt(r) for r in summary],
            "timeline": [fmt(r) for r in timeline]
        }

    except Exception as e:
        log.exception("get_activity failed")
        return JSONResponse({"error": str(e)}, status_code=500)

    finally:
        gcur.close()
        gasman_db.close()
