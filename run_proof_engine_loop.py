# run_proof_engine_loop.py
"""
GASMAN – Proof Engine Runner
----------------------------
✔ Handles infinite loop
✔ PM2 safe
✔ Graceful shutdown
"""

import time
import signal
import sys
from datetime import datetime
from services.proof_engine import run_proof_engine

INTERVAL = 60
RUNNING = True


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def shutdown_handler(signum, frame):
    global RUNNING
    log(f"Shutdown signal received ({signum}), stopping proof engine...")
    RUNNING = False


signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)


if __name__ == "__main__":
    log("GASMAN Proof Engine started")

    while RUNNING:
        start = time.time()

        try:
            run_proof_engine()
        except Exception as e:
            log(f"ERROR in proof engine: {e}")

        elapsed = time.time() - start
        sleep_for = max(5, INTERVAL - elapsed)
        time.sleep(sleep_for)

    log("GASMAN Proof Engine stopped")
    sys.exit(0)
