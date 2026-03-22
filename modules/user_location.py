# modules/user_location.py
"""
GASMAN – USER LOCATION INGEST (REAL-TIME VERSION)
-------------------------------------------------
✔ Stores GPS history
✔ Updates watchdog
✔ Publishes Redis live update
✔ Never crashes UI
✔ Industrial safe
"""

from fastapi import APIRouter, Depends
from modules.jwt_auth import get_current_user
from modules.auth_dependency import require_login
from config.db_pool import get_gasman_db
from config.redis_client import redis_client
import json

router = APIRouter(prefix="/user", tags=["User Location"])


@router.post("/location")
def save_user_location(
    data: dict,
    user_payload: dict = Depends(get_current_user),
    _: dict = Depends(require_login)
):
    conn = None
    cur = None

    try:
        user = user_payload["sub"]

        lat = data.get("lat")
        lng = data.get("lng")

        if lat is None or lng is None:
            return {"ok": False}

        conn = get_gasman_db()
        cur = conn.cursor(dictionary=True)

        # --------------------------------------------------
        # 1️⃣ Store location history
        # --------------------------------------------------
        cur.execute("""
            INSERT INTO gasman_user_location_history
                (user_name, lat, lng)
            VALUES (%s, %s, %s)
        """, (user, lat, lng))

        # --------------------------------------------------
        # 2️⃣ Check active task
        # --------------------------------------------------
        cur.execute("""
            SELECT id
            FROM gasman_tasks
            WHERE accepted_by = %s
              AND status IN ('ASSIGNED','EN_ROUTE','ON_SITE','FILLING','FILLED')
            LIMIT 1
        """, (user,))

        task = cur.fetchone()

        if task:

            task_id = task["id"]

            # Update heartbeat
            cur.execute("""
                UPDATE gasman_tasks
                SET last_ping_at = NOW()
                WHERE id = %s
            """, (task_id,))

            # --------------------------------------------------
            # 3️⃣ Publish Redis real-time event
            # --------------------------------------------------
            try:
                redis_client.publish(
                    "user_location",
                    json.dumps({
                        "task_id": task_id,
                        "user_name": user,
                        "lat": lat,
                        "lng": lng
                    })
                )
            except Exception as redis_err:
                print("REDIS PUBLISH ERROR:", redis_err)

        conn.commit()

    except Exception as e:
        print("USER LOCATION ERROR:", e)
        if conn:
            conn.rollback()

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return {"ok": True}
