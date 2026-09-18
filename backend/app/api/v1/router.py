from fastapi import APIRouter

from app.api.v1 import auth, inventory, master, purchase, roles, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(master.router)
api_router.include_router(purchase.router)
api_router.include_router(inventory.router)
