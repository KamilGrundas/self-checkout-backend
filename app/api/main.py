from fastapi import APIRouter

from app.api.routes import (
    api_keys,
    categories,
    checkout_counters,
    checkout_sessions,
    items,
    login,
    private,
    products,
    system_settings,
    users,
    utils,
    ws,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(api_keys.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(products.router)
api_router.include_router(system_settings.router)
api_router.include_router(categories.router)
api_router.include_router(checkout_counters.router)
api_router.include_router(checkout_sessions.router)
api_router.include_router(ws.router)


if settings.ENVIRONMENT == "local" and settings.LOCAL_SIGNUP_ENABLED:
    api_router.include_router(private.router)
