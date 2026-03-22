# config/db_pool.py
"""
MySQL connection pools for GASMAN
Supports:
- data_logger (legacy system)
- gasman (application DB)
"""

from mysql.connector import pooling
from config.settings import (
    DB_HOST,
    DB_PORT,
    DB_USER,
    DB_PASSWORD,
    DATA_LOGGER_DB,
    GASMAN_DB
)

_POOL_SIZE = 10 #10

# =========================================================
# DATA_LOGGER POOL
# =========================================================
data_logger_pool = pooling.MySQLConnectionPool(
    pool_name="data_logger_pool",
    pool_size=_POOL_SIZE,
    pool_reset_session=True,
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DATA_LOGGER_DB,
    autocommit=True
)

# =========================================================
# GASMAN POOL
# =========================================================
gasman_pool = pooling.MySQLConnectionPool(
    pool_name="gasman_pool",
    pool_size=_POOL_SIZE,
    pool_reset_session=True,
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASSWORD,
    database=GASMAN_DB,
    autocommit=True
)


# =========================================================
# GET CONNECTION HELPERS
# =========================================================
def get_data_logger_db():
    return data_logger_pool.get_connection()


def get_gasman_db():
    return gasman_pool.get_connection()
