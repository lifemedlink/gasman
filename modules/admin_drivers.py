from fastapi import Depends
from modules.jwt_auth import get_current_user
from modules.auth_dependency import require_admin
# modules/admin_drivers.py
"""
ADMIN DRIVER LEADERBOARD – GASMAN
---------------------------------
✔ Uses performance_calc engine
✔ Read-only
✔ Admin-only
✔ JSON-safe
"""

from fastapi import APIRouter, Depends

from services.performance_calc import get_driver_ranking

router = APIRouter(prefix="/admin", tags=["Admin Drivers"])


@router.get("/drivers/ranking")
def driver_ranking(_: dict = Depends(require_admin)):
    """
    Top drivers by performance score
    """
    return get_driver_ranking(days=30, limit=20)
