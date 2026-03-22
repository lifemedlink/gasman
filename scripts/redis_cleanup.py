#!/usr/bin/env python3
"""
Redis cleanup script – GASMAN
--------------------------------
✔ Clears stale device:* keys
✔ Clears classification sets
✔ Safe to run anytime
"""

import sys
import os

# ✅ Fix Python path (CRITICAL)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from config.redis_client import redis_client


def cleanup():
    print("🧹 Cleaning Redis device cache...")

    deleted = 0

    # Remove device hashes
    for key in redis_client.scan_iter("device:*"):
        redis_client.delete(key)
        deleted += 1

    # Remove classification sets
    for key in [
        "devices:critical",
        "devices:low",
        "devices:normal",
        "devices:offline"
    ]:
        redis_client.delete(key)

    print(f"✅ Redis cleanup complete ({deleted} device keys removed)")


if __name__ == "__main__":
    cleanup()
