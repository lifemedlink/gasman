# services/notification_engine.py
"""
NOTIFICATION ENGINE – GASMAN
----------------------------
Centralized notification logic for GASMAN.

PHASE-1 SCOPE (FINAL):
---------------------
✔ Admin / Subadmin alerts
✔ Driver alerts
✔ Redis-based (fast, async)
✔ NO DB schema changes
✔ SAFE for shared data_logger DB

CURRENT DELIVERY:
-----------------
- Console logs (for PM2)
- Redis Pub/Sub (future: push, SMS, WhatsApp)

FUTURE (Phase-2):
-----------------
- Web Push
- SMS / WhatsApp
- Email
"""

import json
import logging
from datetime import datetime
from config.redis_client import redis_client

log = logging.getLogger("gasman.notification")

# ============================
# REDIS CHANNELS (STANDARD)
# ============================
REDIS_CHANNELS = {
    "ADMIN": "gasman_notify_admin",
    "USER": "gasman_notify_user"
}


# ============================
# CORE PUBLISHER
# ============================
def _publish(channel: str, payload: dict):
    """
    Publish notification to Redis channel
    """
    payload["ts"] = datetime.utcnow().isoformat()
    try:
        redis_client.publish(channel, json.dumps(payload))
        log.info(f"NOTIFY → {channel}: {payload}")
    except Exception:
        log.exception("Redis publish failed")


# ============================
# ADMIN / SUBADMIN ALERTS
# ============================
def notify_admin_low(device_id, gas_percent, location=None):
    """
    Device entered LOW gas state
    """
    _publish(
        REDIS_CHANNELS["ADMIN"],
        {
            "type": "DEVICE_LOW",
            "device_id": device_id,
            "gas_percent": gas_percent,
            "location": location
        }
    )


def notify_admin_critical(device_id, gas_percent, location=None):
    """
    Device entered CRITICAL gas state
    """
    _publish(
        REDIS_CHANNELS["ADMIN"],
        {
            "type": "DEVICE_CRITICAL",
            "device_id": device_id,
            "gas_percent": gas_percent,
            "location": location
        }
    )


def notify_admin_sla_breach(task_id, device_id, breach_type, minutes):
    """
    SLA violation alert
    """
    _publish(
        REDIS_CHANNELS["ADMIN"],
        {
            "type": "SLA_BREACH",
            "task_id": task_id,
            "device_id": device_id,
            "breach": breach_type,
            "delay_minutes": minutes
        }
    )


# ============================
# DRIVER / USER ALERTS
# ============================
def notify_user_task_assigned(user_name, device_id, tracking_id):
    """
    Task assigned (manual / auto)
    """
    _publish(
        REDIS_CHANNELS["USER"],
        {
            "type": "TASK_ASSIGNED",
            "user": user_name,
            "device_id": device_id,
            "tracking_id": tracking_id
        }
    )


def notify_user_navigation_start(user_name, device_id):
    """
    Driver started navigation
    """
    _publish(
        REDIS_CHANNELS["USER"],
        {
            "type": "NAVIGATION_STARTED",
            "user": user_name,
            "device_id": device_id
        }
    )


def notify_user_task_completed(user_name, device_id, tracking_id):
    """
    Gas filling completed
    """
    _publish(
        REDIS_CHANNELS["USER"],
        {
            "type": "TASK_COMPLETED",
            "user": user_name,
            "device_id": device_id,
            "tracking_id": tracking_id
        }
    )


# ============================
# PREDICTIVE ALERTS
# ============================
def notify_predictive_refill(device_id, eta_minutes, current_percent):
    """
    Predictive refill warning before LOW
    """
    _publish(
        REDIS_CHANNELS["ADMIN"],
        {
            "type": "PREDICTIVE_REFILL",
            "device_id": device_id,
            "eta_minutes": eta_minutes,
            "gas_percent": current_percent
        }
    )
