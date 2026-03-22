# services/predictive_engine.py
"""
PREDICTIVE GAS REFILL ENGINE – GASMAN
------------------------------------
Uses historical gas_level trends to predict
CRITICAL threshold before it happens.

NO DB MODIFICATIONS.
READ-ONLY.
SAFE FOR PROD.

DATA SOURCES:
-------------
- device_log_historical (gas_level, log_time)
- analog (ang3_lower_limit, ang3_upper_limit)
"""

from datetime import datetime, timedelta
from statistics import mean
from config.db_pool import get_data_logger_db
# =========================
# CONFIG
# =========================
MIN_POINTS = 6            # minimum samples required
PREDICT_WINDOW_MIN = 120  # lookback window (minutes)
CRITICAL_BUFFER_MIN = 30  # warn before reaching CRITICAL


# =========================
# HELPERS
# =========================
def _minutes(a, b):
    return (b - a).total_seconds() / 60


def _safe_float(v):
    try:
        return float(v)
    except Exception:
        return None


# =========================
# GAS PERCENT CALCULATION
# =========================
def gas_percent(mv, low_mv, high_mv):
    """
    Convert millivolts to percentage
    """
    if mv is None or high_mv <= low_mv:
        return None
    pct = (mv - low_mv) / (high_mv - low_mv) * 100
    return max(0, min(100, round(pct, 2)))


# =========================
# CORE PREDICTION
# =========================
def predict_device(device_id: str) -> dict | None:
    """
    Predict when device will reach CRITICAL
    """
    db = get_data_logger_db()
    try:
        cur = db.cursor(dictionary=True)

        # 1️⃣ Limits from analog
        cur.execute("""
            SELECT ang3_lower_limit, ang3_upper_limit
            FROM data_logger.analog
            WHERE device_id = %s
        """, (device_id,))
        limits = cur.fetchone()
        if not limits:
            return None

        low_mv = limits["ang3_lower_limit"]
        high_mv = limits["ang3_upper_limit"]

        # 2️⃣ Recent gas samples
        cur.execute("""
            SELECT gas_level, log_time
            FROM data_logger.device_log_historical
            WHERE device_id = %s
              AND log_time >= NOW() - INTERVAL %s MINUTE
            ORDER BY log_time ASC
        """, (device_id, PREDICT_WINDOW_MIN))
        rows = cur.fetchall()

        if len(rows) < MIN_POINTS:
            return None

        # 3️⃣ Convert to percentage + rate
        samples = []
        for r in rows:
            pct = gas_percent(
                _safe_float(r["gas_level"]),
                low_mv,
                high_mv
            )
            if pct is not None:
                samples.append((r["log_time"], pct))

        if len(samples) < MIN_POINTS:
            return None

        # 4️⃣ Consumption rate (negative slope)
        deltas = []
        for i in range(1, len(samples)):
            t1, p1 = samples[i - 1]
            t2, p2 = samples[i]
            dt = _minutes(t1, t2)
            if dt > 0:
                deltas.append((p2 - p1) / dt)

        avg_rate = mean(deltas) if deltas else 0

        # If gas is increasing (refill ongoing)
        if avg_rate >= 0:
            return {
                "device_id": device_id,
                "status": "REFILLING",
                "current_pct": samples[-1][1]
            }

        # 5️⃣ Predict CRITICAL reach
        current_pct = samples[-1][1]
        minutes_to_critical = (current_pct - 0) / abs(avg_rate)

        eta = samples[-1][0] + timedelta(minutes=minutes_to_critical)

        return {
            "device_id": device_id,
            "current_pct": current_pct,
            "consumption_pct_per_min": round(avg_rate, 4),
            "minutes_to_critical": round(minutes_to_critical, 1),
            "eta_critical": eta.strftime("%Y-%m-%d %H:%M:%S"),
            "alert": minutes_to_critical <= CRITICAL_BUFFER_MIN
        }

    finally:
        try:
            cur.close()
            db.close()
        except Exception:
            pass


# =========================
# BULK PREDICTION (ADMIN)
# =========================
def predict_all_devices(limit: int = 500) -> list:
    """
    Predict for all active devices (admin dashboard)
    """
    db = get_data_logger_db()
    try:
        cur = db.cursor(dictionary=True)

        cur.execute("""
            SELECT DISTINCT device_id
            FROM device_log_historical
            ORDER BY device_id
            LIMIT %s
        """, (limit,))
        devices = [r["device_id"] for r in cur.fetchall()]

        predictions = []
        for d in devices:
            p = predict_device(d)
            if p and p.get("alert"):
                predictions.append(p)

        return predictions

    finally:
        try:
            cur.close()
            db.close()
        except Exception:
            pass
