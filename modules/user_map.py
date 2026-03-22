from fastapi import Depends
from modules.jwt_auth import get_current_user
from modules.auth_dependency import require_login
# modules/user_map.py
"""
GASMAN – USER MAP API (PRODUCTION FINAL)
---------------------------------------
✔ User-safe
✔ No admin dependency
✔ No Redis coupling
✔ Single source of truth (user_devices)
✔ Prevents pin mismatch & flicker
✔ Backward-compatible endpoint
"""

from fastapi import APIRouter, Request, Depends
from modules.auth_dependency import require_admin


# 🔒 Explicit alias to avoid name shadowing
from modules.user_devices import user_map_devices as _user_map_devices

router = APIRouter()


@router.get("/user/map/devices")
def user_map_devices_proxy(
    request: Request,
    _: dict = Depends(require_login)
):
    """
    Backward-compatible USER MAP endpoint.

    Internally delegates to:
      GET /user/devices/map

    Frontend SHOULD prefer:
      /user/devices/map

    This wrapper exists only to avoid breaking older JS.
    """
    return _user_map_devices(request)
