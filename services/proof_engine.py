# services/proof_engine.py
"""
GASMAN – PROOF ENGINE (SINGLE CYCLE)
------------------------------------
✔ Executes ONE proof cycle
✔ No infinite loop
✔ DB safe
✔ Called by runner
"""

from config.db_pool import get_gasman_db

COMPLETE_THRESHOLD = 85
STABLE_REQUIRED = 3


def run_proof_engine():
    """
    Execute one proof engine cycle.
    """

    db = get_gasman_db()
    cur = db.cursor(dictionary=True)

    try:
        cur.execute("""
            SELECT id, device_id, status
            FROM gasman_tasks
            WHERE status IN ('ACCEPTED','IN_PROGRESS')
        """)
        tasks = cur.fetchall()

        for t in tasks:
            task_id = t["id"]
            device_id = t["device_id"]
            status = t["status"]

            cur.execute("""
                SELECT gas_percentage, online
                FROM gasman_device_status
                WHERE device_id = %s
            """, (device_id,))
            d = cur.fetchone()

            if not d or not d["online"]:
                continue

            gas_pct = int(d["gas_percentage"])

            # AUTO START
            if status == "ACCEPTED" and gas_pct >= COMPLETE_THRESHOLD - 10:
                cur.execute("""
                    UPDATE gasman_tasks
                    SET status = 'IN_PROGRESS',
                        started_navigation_at = NOW()
                    WHERE id = %s AND status = 'ACCEPTED'
                """, (task_id,))

            # STABILITY TRACK
            cur.execute("""
                SELECT stable_count, last_gas_percent
                FROM gasman_task_gas_state
                WHERE task_id = %s
            """, (task_id,))
            state = cur.fetchone()

            if not state:
                cur.execute("""
                    INSERT INTO gasman_task_gas_state
                    (task_id, last_gas_percent, stable_count)
                    VALUES (%s, %s, 0)
                """, (task_id, gas_pct))
                db.commit()
                continue

            stable = state["stable_count"]
            last = state["last_gas_percent"]

            if gas_pct >= COMPLETE_THRESHOLD and gas_pct >= last:
                stable += 1
            else:
                stable = 0

            # AUTO COMPLETE
            if status == "IN_PROGRESS" and stable >= STABLE_REQUIRED:
                cur.execute("""
                    UPDATE gasman_tasks
                    SET status = 'COMPLETED',
                        completed_at = NOW()
                    WHERE id = %s AND status = 'IN_PROGRESS'
                """, (task_id,))

                cur.execute("""
                    DELETE FROM gasman_task_gas_state
                    WHERE task_id = %s
                """, (task_id,))
            else:
                cur.execute("""
                    UPDATE gasman_task_gas_state
                    SET last_gas_percent = %s,
                        stable_count = %s
                    WHERE task_id = %s
                """, (gas_pct, stable, task_id))

            db.commit()

    except Exception as e:
        db.rollback()
        print("❌ PROOF ENGINE ERROR:", e)

    finally:
        cur.close()
        db.close()
