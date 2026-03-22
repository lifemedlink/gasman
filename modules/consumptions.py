# modules/consumptions.py

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import JSONResponse
from config.db_pool import get_gasman_db, get_data_logger_db
from modules.jwt_auth import get_current_user
from decimal import Decimal

router = APIRouter(prefix="/admin", tags=["Admin Consumptions"])


# =========================================================
# ADMIN DEPENDENCY
# =========================================================
def require_admin(user: dict = Depends(get_current_user)):
    if not user or user.get("role") not in ("admin", "subadmin"):
        return None
    return user


def dec(v):
    return float(v) if isinstance(v, Decimal) else v


# =========================================================
# GAS PARAMETERS
# =========================================================
@router.get("/gas-parameters")
def get_gas_parameters(user: dict = Depends(require_admin)):

    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    db = get_gasman_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT molecular_weight_M,
               specific_gravity_S,
               operating_pressure_LP,
               temperature_T,
               gas_constant_G
        FROM gasman_gas_parameters
        WHERE is_active = 1
        ORDER BY updated_at DESC
        LIMIT 1
    """)

    row = cur.fetchone()

    cur.close()
    db.close()

    return JSONResponse({k: dec(v) for k, v in row.items()} if row else {})


@router.post("/gas-parameters")
async def update_gas_parameters(
    request: Request,
    user: dict = Depends(require_admin)
):

    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    data = await request.json()

    if data.get("password") != "admin@123":
        return JSONResponse({"error": "invalid password"}, status_code=403)

    M = float(data["M"])
    S = float(data["S"])
    LP = float(data["LP"])
    T = float(data["T"])

    # SAME FORMULA (no change as requested)
    G = (1 / (((22.4 * (273.15 + T) / 273.15) / M * 1.013) / (LP + 1.013))) / S

    db = get_gasman_db()
    cur = db.cursor()

    cur.execute("UPDATE gasman_gas_parameters SET is_active = 0")

    cur.execute("""
        INSERT INTO gasman_gas_parameters
        (molecular_weight_M,
         specific_gravity_S,
         operating_pressure_LP,
         temperature_T,
         gas_constant_G,
         updated_by,
         is_active)
        VALUES (%s,%s,%s,%s,%s,%s,1)
    """, (M, S, LP, T, G, user["sub"]))

    db.commit()
    cur.close()
    db.close()

    return JSONResponse({"status": "ok", "G": round(G, 6)})


# =========================================================
# CONSUMPTIONS
# =========================================================
@router.get("/consumptions/data")
def get_consumptions(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    user: dict = Depends(require_admin)
):

    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    db = get_data_logger_db()
    cur = db.cursor(dictionary=True)

    if start_date and end_date:
        cur.execute("""
            SELECT
              d.device_id,
              d.customer_name,
              d.address AS location,

              d.meter1 AS m1_sl,
              MIN(h.meter1) AS m1_start,
              MAX(h.meter1) AS m1_end,

              d.meter2 AS m2_sl,
              MIN(h.meter2) AS m2_start,
              MAX(h.meter2) AS m2_end,

              d.meter3 AS m3_sl,
              MIN(h.meter3) AS m3_start,
              MAX(h.meter3) AS m3_end,

              d.meter4 AS m4_sl,
              MIN(h.meter4) AS m4_start,
              MAX(h.meter4) AS m4_end

            FROM device_log_historical h
            JOIN devicelist d ON d.device_id = h.device_id
            WHERE h.log_time BETWEEN %s AND %s
            GROUP BY d.device_id
        """, (f"{start_date} 00:00:00", f"{end_date} 23:59:59"))

    else:
        cur.execute("""
            SELECT
              d.device_id,
              d.customer_name,
              d.address AS location,

              d.meter1 AS m1_sl,
              h.meter1 AS m1_start,
              h.meter1 AS m1_end,

              d.meter2 AS m2_sl,
              h.meter2 AS m2_start,
              h.meter2 AS m2_end,

              d.meter3 AS m3_sl,
              h.meter3 AS m3_start,
              h.meter3 AS m3_end,

              d.meter4 AS m4_sl,
              h.meter4 AS m4_start,
              h.meter4 AS m4_end

            FROM device_log_historical h
            JOIN devicelist d ON d.device_id = h.device_id
            JOIN (
              SELECT device_id, MAX(log_time) t
              FROM device_log_historical
              GROUP BY device_id
            ) x ON x.device_id = h.device_id AND x.t = h.log_time
        """)

    rows = cur.fetchall()

    cur.close()
    db.close()

    return JSONResponse(rows)
