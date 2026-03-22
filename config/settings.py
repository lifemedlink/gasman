# config/settings.py
"""
Central configuration for GASMAN
- Single source for DB, Redis, Google Maps
- Safe for GCP / VM / Docker
"""

import os

# ===============================
# ENVIRONMENT
# ===============================
ENV = os.getenv("ENV", "prod").lower()

DEBUG = ENV != "prod"

# ===============================
# DATABASE (MySQL - data_logger)
# ===============================
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")

DATA_LOGGER_DB = os.getenv("DATA_LOGGER_DB", "data_logger")
GASMAN_DB = os.getenv("GASMAN_DB","gasman")
# ===============================
# JWT SECRET
# ===============================
JWT_SECRET = os.getenv("JWT_SECRET")

if not JWT_SECRET or len(JWT_SECRET) < 64:
    raise RuntimeError("JWT_SECRET must be 64 hex characters (32 bytes)")

# ===============================
# GOOGLE MAPS (SINGLE SOURCE)
# Used by:
# - admin dashboard
# - user drive mode
# ===============================
GOOGLE_MAPS_API_KEY = os.getenv(
    "GOOGLE_MAPS_API_KEY",
    ""  # keep empty in repo, set via ENV in prod
)

# ===============================
# REDIS (FAST CACHE + LIVE MAP)
# ===============================
REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://127.0.0.1:6379/0"
)

# ===============================
# APP LIMITS (SAFE DEFAULTS)
# ===============================
MAX_DEVICES = int(os.getenv("MAX_DEVICES", 5000))
MAX_USERS = int(os.getenv("MAX_USERS", 200))
