# ws/device_ws.py
"""
GASMAN – DEVICE WEBSOCKET ENGINE (STABLE VERSION)
✔ Single WS endpoint
✔ Redis pub/sub fanout
✔ Admin + User routing
✔ Safe JSON parsing
✔ Auto-recover listener
"""

import json
import asyncio
import logging
from typing import Set, Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config.redis_client import redis_client

log = logging.getLogger("gasman.ws")

router = APIRouter()

# ============================================================
# CONNECTION REGISTRY
# ============================================================

ADMIN_CLIENTS: Set[WebSocket] = set()
USER_CLIENTS: Dict[str, Set[WebSocket]] = {}

# ============================================================
# SAFE SEND
# ============================================================

async def _safe_send(ws: WebSocket, payload: dict):
    try:
        await ws.send_text(json.dumps(payload))
    except Exception:
        pass

# ============================================================
# USER REGISTRY
# ============================================================

def _register_user(ws: WebSocket, user_name: str):
    USER_CLIENTS.setdefault(user_name, set()).add(ws)

def _unregister_user(ws: WebSocket, user_name: str):
    if user_name in USER_CLIENTS:
        USER_CLIENTS[user_name].discard(ws)
        if not USER_CLIENTS[user_name]:
            del USER_CLIENTS[user_name]

# ============================================================
# BROADCAST (THIS WAS MISSING)
# ============================================================

async def _broadcast(payload: dict):
    """
    Routing:
    - Admin/Subadmin → everything
    - User → user_name / assigned_user match
    """

    # Admins
    for ws in list(ADMIN_CLIENTS):
        await _safe_send(ws, payload)

    # User specific
    user = payload.get("user_name") or payload.get("assigned_user")
    if user and user in USER_CLIENTS:
        for ws in list(USER_CLIENTS[user]):
            await _safe_send(ws, payload)

# ============================================================
# WEBSOCKET ENDPOINT
# ============================================================

@router.websocket("/ws/devices")
async def device_ws(websocket: WebSocket):

    await websocket.accept()

    role = websocket.query_params.get("role")
    user = websocket.query_params.get("user")

    if role in ("admin", "subadmin"):
        ADMIN_CLIENTS.add(websocket)
        log.info("Admin WS connected")

    elif role == "user" and user:
        _register_user(websocket, user)
        log.info("User WS connected: %s", user)

    else:
        await websocket.close()
        return

    try:
        while True:
            await asyncio.sleep(30)

    except WebSocketDisconnect:
        pass

    finally:
        ADMIN_CLIENTS.discard(websocket)
        if role == "user" and user:
            _unregister_user(websocket, user)
        log.info("WS disconnected")

# ============================================================
# REDIS LISTENER
# ============================================================

async def _redis_listener():

    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe("device_updates", "user_location", "notifications", "task_update")

    log.info("Redis WS listener started")

    while True:
        try:
            msg = pubsub.get_message(timeout=0.5)

            if not msg:
                await asyncio.sleep(0.05)
                continue

            channel = msg["channel"]
            if isinstance(channel, bytes):
                channel = channel.decode()

            try:
                data = json.loads(msg["data"])
            except Exception:
                continue

            payload = {
                "topic": channel,
                **data
            }

            await _broadcast(payload)

        except Exception:
            log.exception("WS Redis error")
            await asyncio.sleep(1)

