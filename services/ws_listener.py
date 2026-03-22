import asyncio
import json
import logging
import os
import redis

from ws.device_ws import _redis_listener as device_listener
from ws.session_ws import connections  # reuse connection registry

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gasman.ws.listener")

redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
    decode_responses=True
)


async def session_listener():
    pubsub = redis_client.pubsub()
    pubsub.subscribe("force_logout")

    log.info("Session Redis listener started")

    while True:
        message = pubsub.get_message(ignore_subscribe_messages=True)

        if message:
            username = message["data"]
            ws = connections.get(username)

            if ws:
                try:
                    await ws.send_text(json.dumps({
                        "type": "force_logout"
                    }))
                    log.info(f"Logout pushed to: {username}")
                except Exception:
                    connections.pop(username, None)

        await asyncio.sleep(0.2)


async def main():
    await asyncio.gather(
        device_listener(),
        session_listener()
    )


if __name__ == "__main__":
    asyncio.run(main())
