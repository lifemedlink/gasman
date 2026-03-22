# modules/predictive_alerts.py

from fastapi import APIRouter, Depends
from config.db_pool import get_gasman_db
from modules.auth_dependency import require_admin
from decimal import Decimal

router = APIRouter()


# =========================================================
# PREDICTIVE ALERTS
# =========================================================
@router.get("/admin/predictive-alerts")
def predictive_alerts(_: dict = Depends(require_admin)):

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    try:

        cur.execute("""
            SELECT
                device_id,
                gas_percentage,
                classification
            FROM gasman_device_status
        """)

        rows = cur.fetchall()

        alerts = []

        for r in rows:

            gas = float(r["gas_percentage"])

            if gas < 10:
                alerts.append({
                    "severity": "CRITICAL",
                    "device": r["device_id"],
                    "prediction": "Gas < 10%",
                    "eta": "Immediate"
                })

            elif gas < 25:
                alerts.append({
                    "severity": "WARNING",
                    "device": r["device_id"],
                    "prediction": "Gas will reach CRITICAL soon",
                    "eta": "2-3 hours"
                })

        return alerts

    finally:
        cur.close()
        conn.close()
