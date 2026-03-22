import asyncio
import json
import redis
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
import os

router = APIRouter()

# ---------------------------------------------------
# REDIS CONNECTION
# ---------------------------------------------------
redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
    decode_responses=True
)

connections = {}  # {username: websocket}


# ---------------------------------------------------
# SEND FORCE LOGOUT
# ---------------------------------------------------
async def send_force_logout(username: str):
    redis_client.publish("force_logout", username)


# ---------------------------------------------------
# WEBSOCKET ENDPOINT
# ---------------------------------------------------
@router.websocket("/ws/session/{username}")
async def session_ws(websocket: WebSocket, username: str):
    await websocket.accept()

    connections[username] = websocket
    print("WS connected:", username)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connections.pop(username, None)
        print("WS disconnected:", username)


