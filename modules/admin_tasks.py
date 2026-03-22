# modules/admin_tasks.py

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from config.db_pool import get_gasman_db
from modules.auth_dependency import require_admin

router = APIRouter(prefix="/admin/tasks", tags=["Admin Tasks"])


@router.get("/live")
def live_tasks(_: dict = Depends(require_admin)):

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT
            t.id,
            t.device_id,
            t.accepted_by AS driver,
            t.status,
            t.tracking_id,
            t.accepted_at,

            -- DEVICE STATUS DATA
            ds.gas_percentage,
            ds.classification,
            ds.coordinates,
            ds.device_location

        FROM gasman_tasks t

        LEFT JOIN gasman_device_status ds
            ON ds.device_id = t.device_id

        WHERE
            t.accepted_by IS NOT NULL
            AND t.status NOT IN (
                'PENDING',
                'REJECTED',
                'COMPLETED',
                'CANCELLED'
            )

        ORDER BY t.updated_at DESC
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return jsonable_encoder(rows)


@router.get("/{task_id}")
def task_timeline(task_id: int, _: dict = Depends(require_admin)):

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT
            created_at,
            action,
            status_after,
            note
        FROM gasman_task_activity
        WHERE task_id = %s
        ORDER BY created_at
    """, (task_id,))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return jsonable_encoder(rows)
