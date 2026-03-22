# config/redis_client.py
"""
Redis Client Configuration (Enterprise Production Safe)

✔ Connection pooling
✔ Auto reconnect
✔ Timeout protection
✔ SSL support
✔ Health check
✔ Safe fallback
✔ Structured logging
"""

import os
import redis
import logging

log = logging.getLogger("gasman.redis")

# =========================================================
# ENV CONFIG
# =========================================================

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", 50))
REDIS_SOCKET_TIMEOUT = int(os.getenv("REDIS_SOCKET_TIMEOUT", 5))
REDIS_CONNECT_TIMEOUT = int(os.getenv("REDIS_CONNECT_TIMEOUT", 5))

# =========================================================
# CONNECTION POOL
# =========================================================

pool = redis.ConnectionPool.from_url(
    REDIS_URL,
    max_connections=REDIS_MAX_CONNECTIONS,
    socket_timeout=REDIS_SOCKET_TIMEOUT,
    socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
    retry_on_timeout=True,
    decode_responses=True
)

redis_client = redis.Redis(connection_pool=pool)

# =========================================================
# HEALTH CHECK
# =========================================================

def check_redis():
    """
    Ping Redis to verify connection.
    Safe to call at startup.
    """
    try:
        redis_client.ping()
        log.info("Redis connection established")
        return True
    except Exception as e:
        log.error("Redis connection failed: %s", str(e))
        return False

# Optional: Check on import (safe in prod)
check_redis()

# =========================================================
# SAFE WRAPPER (OPTIONAL UTILITY)
# =========================================================

def safe_get(key: str):
    try:
        return redis_client.get(key)
    except Exception as e:
        log.warning("Redis GET failed for key=%s error=%s", key, str(e))
        return None


def safe_set(key: str, value: str, ex: int | None = None):
    try:
        redis_client.set(key, value, ex=ex)
    except Exception as e:
        log.warning("Redis SET failed for key=%s error=%s", key, str(e))


def safe_delete(key: str):
    try:
        redis_client.delete(key)
    except Exception as e:
        log.warning("Redis DELETE failed for key=%s error=%s", key, str(e))
