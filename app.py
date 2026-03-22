"""
GASMAN – ENTERPRISE JWT + REDIS VERSION

✔ JWT Authentication
✔ Redis Session Binding
✔ Forced Device Invalidation
✔ PM2 + Gunicorn Safe
✔ Production Middleware Order
✔ No Starlette SessionMiddleware
✔ Horizontal Scaling Ready
"""

from fastapi import FastAPI, Request, Depends
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    JSONResponse,
    PlainTextResponse
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_302_FOUND

import logging
import traceback
from decimal import Decimal
from fastapi.encoders import jsonable_encoder

from config.settings import GOOGLE_MAPS_API_KEY
from modules.auth_dependency import get_current_user, require_admin

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
log = logging.getLogger("gasman")

# =========================================================
# FASTAPI INIT
# =========================================================
app = FastAPI(
    title="GASMAN",
    debug=False
)

# =========================================================
# DECIMAL SAFE JSON
# =========================================================
class DecimalSafeJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return super().render(
            jsonable_encoder(
                content,
                custom_encoder={Decimal: float}
            )
        )

app.default_response_class = DecimalSafeJSONResponse

# =========================================================
# GLOBAL ERROR GUARD
# =========================================================
@app.middleware("http")
async def global_error_guard(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        log.error("UNHANDLED SERVER ERROR")
        log.error(traceback.format_exc())
        return PlainTextResponse("Internal Server Error", status_code=500)

# =========================================================
# STATIC & TEMPLATES
# =========================================================
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# =========================================================
# AUTH ROUTER
# =========================================================
from modules.auth import router as auth_router
app.include_router(auth_router)

# =========================================================
# ADMIN ROUTERS
# =========================================================
from modules.devices import router as admin_devices_router
from modules.activity import router as activity_router
from modules.consumptions import router as consumptions_router
from modules.users import router as users_router
from modules.admin_tasks import router as admin_tasks_router
from modules.admin_map import router as admin_map_router
from modules.admin_analytics import router as admin_analytics_router
from modules.predictive_alerts import router as admin_predictive_router
from modules.admin_drivers import router as admin_drivers_router
from modules.admin_sessions import router as admin_sessions_router
from modules.admin_users import router as admin_users_router
from modules.admin_database import router as admin_database_router
# =========================================================
# USER ROUTERS
# =========================================================
from modules.user_map import router as user_map_router
from modules.user_location import router as user_location_router
from modules.user_tasks import router as user_tasks_router
from modules.user_devices import router as user_devices_router
from modules.user_settings import router as user_settings_router
from modules.user_activity import router as user_activity_router

# =========================================================
# WEBSOCKET ROUTERS
# =========================================================
from ws.device_ws import router as ws_router
from ws.session_ws import router as session_ws_router

# Register All Routers
app.include_router(admin_devices_router)
app.include_router(activity_router)
app.include_router(consumptions_router)
app.include_router(users_router)
app.include_router(admin_tasks_router)
app.include_router(admin_map_router)
app.include_router(admin_analytics_router)
app.include_router(admin_predictive_router)
app.include_router(admin_drivers_router)
app.include_router(admin_sessions_router)
app.include_router(admin_users_router)
app.include_router(admin_database_router)

app.include_router(user_map_router)
app.include_router(user_location_router)
app.include_router(user_tasks_router)
app.include_router(user_devices_router)
app.include_router(user_settings_router)
app.include_router(user_activity_router)


app.include_router(ws_router)
app.include_router(session_ws_router)

# =========================================================
# TEMPLATE CONTEXT
# =========================================================
def get_user_context(user_payload: dict | None):
    return {
        "user_name": user_payload.get("sub") if user_payload else None,
        "role": user_payload.get("role") if user_payload else None,
        "config": {
            "GOOGLE_MAPS_API_KEY": GOOGLE_MAPS_API_KEY
        }
    }

# =========================================================
# ROOT
# =========================================================
@app.get("/")
async def root(request: Request):

    access_token = request.cookies.get("access_token")

    if not access_token:
        return RedirectResponse("/login", status_code=302)

    user = get_current_user(request)

    if isinstance(user, RedirectResponse):
        return user

    if user.get("role") in ("admin", "subadmin"):
        return RedirectResponse("/admin", status_code=302)

    return RedirectResponse("/user", status_code=302)

# =========================================================
# LOGIN PAGE
# =========================================================
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, msg: str | None = None):
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "msg": msg
        }
    )

# =========================================================
# ADMIN HTML
# =========================================================
@app.get("/admin", response_class=HTMLResponse)
async def admin_home(request: Request, user=Depends(require_admin)):

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        "admin_dashboard.html",
        {"request": request, **get_user_context(user)}
    )

@app.get("/admin/devices", response_class=HTMLResponse)
async def admin_devices(request: Request, user=Depends(require_admin)):

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        "admin_devices.html",
        {"request": request, **get_user_context(user)}
    )

@app.get("/admin/activity", response_class=HTMLResponse)
async def admin_activity(request: Request, user=Depends(require_admin)):

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        "admin_activity.html",
        {"request": request, **get_user_context(user)}
    )

@app.get("/admin/consumptions", response_class=HTMLResponse)
async def admin_consumptions(request: Request, user=Depends(require_admin)):

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        "admin_consumptions.html",
        {"request": request, **get_user_context(user)}
    )

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request, user=Depends(require_admin)):

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        "admin_users.html",
        {"request": request, **get_user_context(user)}
    )

@app.get("/admin/live", response_class=HTMLResponse)
async def admin_live(request: Request, user=Depends(require_admin)):

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        "admin_live.html",
        {"request": request, **get_user_context(user)}
    )
@app.get("/admin/predictive", response_class=HTMLResponse)
async def admin_predictive(request: Request, user=Depends(require_admin)):

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        "admin_predictive.html",
        {"request": request, **get_user_context(user)}
    )
@app.get("/admin/database", response_class=HTMLResponse)
async def admin_database(request: Request, user=Depends(require_admin)):

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        "admin_database.html",
        {"request": request, **get_user_context(user)}
    )

# =========================================================
# USER HTML
# =========================================================
@app.get("/user", response_class=HTMLResponse)
async def user_home(request: Request, user=Depends(get_current_user)):

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        "user_home.html",
        {"request": request, **get_user_context(user)}
    )

@app.get("/user/devices", response_class=HTMLResponse)
async def user_devices(request: Request, user=Depends(get_current_user)):

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        "user_devices.html",
        {"request": request, **get_user_context(user)}
    )

@app.get("/user/activity", response_class=HTMLResponse)
async def user_activity(request: Request, user=Depends(get_current_user)):

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        "user_activity.html",
        {"request": request, **get_user_context(user)}
    )


# =========================================================
# HEALTH
# =========================================================
@app.get("/health")
async def health():
    return {"status": "ok"}
