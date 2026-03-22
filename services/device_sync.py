# services/device_sync.py
"""
GASMAN – DEVICE SYNC ENGINE (ENTERPRISE CLEAN VERSION)
-------------------------------------------------------
✔ DB = single source of truth
✔ Redis = live cache + pub/sub
✔ No task lifecycle logic here
✔ No hybrid FSM
✔ Publish only when device state changes
✔ Structured logging
✔ Safe comparison
✔ Production stable loop
"""

import time
import json
import logging
from decimal import Decimal
from config.db_pool import get_gasman_db
from config.redis_client import redis_client

# ============================================
# CONFIG
# ============================================

SYNC_INTERVAL = 10  # seconds (10 = real-time feel, safe load)

log = logging.getLogger("gasman.device_sync")


# ============================================
# SAFE SERIALIZER
# ============================================

def normalize_payload(row: dict) -> dict:
    """
    Convert DB row to Redis-safe payload
    """
    return {
        "device_id": row["device_id"],
        "classification": row["classification"],
        "gas_percent": float(row["gas_percentage"]) if row["gas_percentage"] is not None else 0.0,
        "coordinates": (row["coordinates"] or "").replace(" ", ""),
        "online": int(row["online"]),
        "updated_at": row["updated_at"].strftime("%Y-%m-%d %H:%M:%S")
        if row["updated_at"] else None
    }


# ============================================
# COMPARE OLD VS NEW
# ============================================

def is_changed(old: dict, new: dict) -> bool:
    """
    Compare Redis hash (string values) with new payload
    """
    if not old:
        return True

    for k, v in new.items():
        if str(old.get(k)) != str(v):
            return True

    return False


# ============================================
# SINGLE SYNC CYCLE
# ============================================

def sync_once():
    db = get_gasman_db()
    cur = db.cursor(dictionary=True)

    try:
        cur.execute("""
            SELECT
                device_id,
                classification,
                gas_percentage,
                coordinates,
                online,
                updated_at
            FROM gasman_device_status
            WHERE coordinates IS NOT NULL
        """)

        rows = cur.fetchall()

        for row in rows:
            payload = normalize_payload(row)
            device_id = payload["device_id"]
            redis_key = f"device:{device_id}"

            # ------------------------------------------
            # 1️⃣ CHECK REDIS CACHE
            # ------------------------------------------
            old = redis_client.hgetall(redis_key)

            if not is_changed(old, payload):
                continue  # no change → skip publish

            # ------------------------------------------
            # 2️⃣ UPDATE REDIS HASH
            # ------------------------------------------
            redis_client.delete(redis_key)
            redis_client.hset(redis_key, mapping=payload)

            # ------------------------------------------
            # 3️⃣ PUBLISH CHANGE EVENT
            # ------------------------------------------
            redis_client.publish(
                "device_updates",
                json.dumps(payload)
            )

        log.info("Device sync cycle complete (%d devices)", len(rows))

    except Exception as e:
        log.exception("DEVICE SYNC ERROR")

    finally:
        cur.close()
        db.close()


# ============================================
# MAIN LOOP
# ============================================

def run_forever():
    log.info("✅ GASMAN Device Sync started (enterprise mode)")

    while True:
        try:
            sync_once()
        except Exception:
            log.exception("Unexpected fatal error in sync loop")

        time.sleep(SYNC_INTERVAL)


# ============================================
# ENTRY
# ============================================

if __name__ == "__main__":
    run_forever()
