"""
GASMAN – ENTERPRISE DATABASE OPERATIONS MODULE

Features
✔ Monitor gasman + data_logger databases
✔ Table size monitoring
✔ Disk usage monitoring
✔ Old log cleanup
✔ Data logger cleanup
✔ Largest table detection
✔ Table optimization
✔ Production-safe SQL queries
"""

from fastapi import APIRouter, Depends, Body
from config.db_pool import get_gasman_db
from modules.auth_dependency import require_admin
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from fastapi.responses import FileResponse
import os
SERVICE_PASSWORD = os.getenv("SERVICE_PASSWORD","service_password")

router = APIRouter()
# ----------------------------------------------------------
# BACKUP DIRECTORY (UNIVERSAL PATH)
# ----------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]
BACKUP_DIR = BASE_DIR / "backups"

BACKUP_DIR.mkdir(parents=True, exist_ok=True)
# ==========================================================
# DATABASE + DISK STATS
# ==========================================================

@router.get("/admin/database-stats")
def database_stats(_: dict = Depends(require_admin)):

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    databases = ["gasman", "data_logger"]

    database_results = []
    total_size = 0

    try:

        for db in databases:

            # --------------------------------------------------
            # TABLE SIZES
            # --------------------------------------------------

            cur.execute("""
                SELECT
                    table_name,
                    IFNULL(table_rows,0) AS table_rows,
                    ROUND(
                        (IFNULL(data_length,0) + IFNULL(index_length,0))
                        /1024/1024,
                        2
                    ) AS size_mb
                FROM information_schema.tables
                WHERE table_schema = %s
                ORDER BY size_mb DESC
            """, (db,))

            tables = cur.fetchall()

            # --------------------------------------------------
            # DATABASE TOTAL SIZE
            # --------------------------------------------------

            cur.execute("""
                SELECT
                    ROUND(
                        SUM(
                            IFNULL(data_length,0) +
                            IFNULL(index_length,0)
                        ) /1024/1024,
                        2
                    ) AS db_size
                FROM information_schema.tables
                WHERE table_schema = %s
            """, (db,))

            result = cur.fetchone()
            size = result["db_size"] if result["db_size"] else 0

            total_size += size

            database_results.append({
                "name": db,
                "size": size,
                "tables": tables
            })

    finally:
        cur.close()
        conn.close()

    # --------------------------------------------------
    # SERVER DISK USAGE
    # --------------------------------------------------

    total, used, free = shutil.disk_usage("/")

    return {
        "databases": database_results,
        "db_total": round(total_size, 2),
        "disk_total": round(total / 1024 / 1024 / 1024, 2),
        "disk_used": round(used / 1024 / 1024 / 1024, 2),
        "disk_free": round(free / 1024 / 1024 / 1024, 2)
    }


# ==========================================================
# OLD GASMAN LOG COUNT
# ==========================================================

@router.get("/admin/old-log-count")
def old_log_count(_ = Depends(require_admin)):

    conn = get_gasman_db()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT COUNT(*)
            FROM gasman_task_activity
            WHERE created_at < NOW() - INTERVAL 90 DAY
        """)

        count = cur.fetchone()[0]

    finally:
        cur.close()
        conn.close()

    return {"old_logs": count}


# ==========================================================
# CLEAN GASMAN LOGS
# ==========================================================

@router.post("/admin/cleanup-gasman")
def cleanup_gasman(_ = Depends(require_admin)):

    conn = get_gasman_db()
    cur = conn.cursor()

    try:

        cur.execute("""
            DELETE FROM gasman_task_activity
            WHERE created_at < NOW() - INTERVAL 90 DAY
        """)

        deleted = cur.rowcount

        conn.commit()

    finally:
        cur.close()
        conn.close()

    return {"deleted": deleted}


# ==========================================================
# CLEAN DATA LOGGER
# ==========================================================

@router.post("/admin/cleanup-datalogger")
def cleanup_datalogger(_ = Depends(require_admin)):

    conn = get_gasman_db()
    cur = conn.cursor()

    raw_deleted = 0
    hist_deleted = 0

    try:

        # --------------------------------------------------
        # RAW TELEMETRY DATA
        # --------------------------------------------------

        cur.execute("""
            DELETE FROM data_logger.raw_table
        """)
        raw_deleted = cur.rowcount

        # --------------------------------------------------
        # HISTORICAL DEVICE LOGS
        # --------------------------------------------------

        cur.execute("""
            DELETE FROM data_logger.device_log_historical
        """)
        hist_deleted = cur.rowcount

        conn.commit()

    except Exception as e:

        conn.rollback()

        return {
            "raw_deleted": 0,
            "historical_deleted": 0,
            "error": str(e)
        }

    finally:
        cur.close()
        conn.close()

    return {
        "raw_deleted": raw_deleted,
        "historical_deleted": hist_deleted
    }


# ==========================================================
# LARGEST TABLE ANALYTICS
# ==========================================================

@router.get("/admin/database-operations")
def database_operations(_ = Depends(require_admin)):

    conn = get_gasman_db()
    cur = conn.cursor(dictionary=True)

    try:

        cur.execute("""
            SELECT
                table_schema,
                table_name,
                IFNULL(table_rows,0) AS table_rows,
                ROUND(
                    (IFNULL(data_length,0) +
                     IFNULL(index_length,0))
                    /1024/1024,
                    2
                ) AS size_mb
            FROM information_schema.tables
            WHERE table_schema IN ('gasman','data_logger')
            ORDER BY size_mb DESC
            LIMIT 50
        """)

        tables = cur.fetchall()

    finally:
        cur.close()
        conn.close()

    return {"largest_tables": tables}


# ==========================================================
# OPTIMIZE TABLES
# ==========================================================

@router.post("/admin/optimize-tables")
def optimize_tables(_ = Depends(require_admin)):

    conn = get_gasman_db()
    cur = conn.cursor()

    optimized = 0

    try:

        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema IN ('gasman','data_logger')
        """)

        tables = cur.fetchall()

        for schema, table in tables:

            try:
                cur.execute(f"OPTIMIZE TABLE {schema}.{table}")
                optimized += 1
            except:
                # skip tables that fail
                pass

        conn.commit()

    finally:
        cur.close()
        conn.close()

    return {
        "status": "optimized",
        "tables_optimized": optimized
    }
# ==========================================================
# CREATE BACKUP
# ==========================================================

@router.post("/admin/create-backup")
def create_backup(_ = Depends(require_admin)):

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    filename = f"gasman_backup_{timestamp}.sql"

    filepath = BACKUP_DIR / filename

    cmd = [
        "mysqldump",
        "-u", "root",
        "-proot",
        "gasman",
        "data_logger"
    ]

    with open(filepath, "w") as f:
        subprocess.run(cmd, stdout=f, check=True)

    return {
        "status": "success",
        "file": filename
    }


# ==========================================================
# LIST BACKUPS
# ==========================================================

@router.get("/admin/list-backups")
def list_backups(_ = Depends(require_admin)):

    files = []

    for path in sorted(BACKUP_DIR.glob("*.sql"), reverse=True):

        files.append({
            "name": path.name,
            "size": round(path.stat().st_size / 1024 / 1024, 2),
            "created": datetime.fromtimestamp(path.stat().st_ctime)
        })

    return {"backups": files}
# ==========================================================
# DOWNLOAD BACKUP
# ==========================================================

@router.get("/admin/download-backup/{file}")
def download_backup(file: str, _ = Depends(require_admin)):

    path = BACKUP_DIR / file

    return FileResponse(
        path,
        filename=file,
        media_type="application/sql"
    )


# ==========================================================
# RESTORE BACKUP
# ==========================================================

@router.post("/admin/restore-backup/{file}")
def restore_backup(file: str, _ = Depends(require_admin)):

    path = BACKUP_DIR / file

    cmd = [
        "mysql",
        "-u", "root",
        "-proot"
    ]

    with open(path, "r") as f:
        subprocess.run(cmd, stdin=f, check=True)

    return {"status": "restored"}
# ==========================================================
# DELETE BACKUP
# ==========================================================

@router.delete("/admin/delete-backup/{file}")
def delete_backup(file: str, _ = Depends(require_admin)):

    try:

        path = BACKUP_DIR / file

        if not path.exists():
            return {"status": "error", "message": "Backup not found"}

        path.unlink()

        return {"status": "deleted", "file": file}

    except Exception as e:

        return {"status": "error", "message": str(e)}
# ==========================================================
# VERIFY SERVICE PASSWORD
# ==========================================================

from fastapi import Body

@router.post("/admin/verify-service-password")
def verify_service_password(data: dict = Body(...), _ = Depends(require_admin)):

    password = data.get("password")

    if password == SERVICE_PASSWORD:
        return {"status": "ok"}

    return {"status": "invalid"}
