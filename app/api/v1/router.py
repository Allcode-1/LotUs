from fastapi import APIRouter

from app.auth.routes import router as auth_router
from app.api.v1.auction import router as auction_router
from app.api.v1.balance import router as balance_router
from app.api.v1.item import router as item_router
from app.api.v1.ws import router as ws_router
# pyarch:router-imports


v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(auth_router)
v1_router.include_router(balance_router)
v1_router.include_router(item_router)
v1_router.include_router(auction_router)
v1_router.include_router(ws_router)
# pyarch:router-includes
