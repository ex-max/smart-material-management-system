from fastapi import APIRouter

from app.api.v1 import (
    auth,
    forecast,
    inventory,
    inventory_ops,
    ledger,
    master,
    operation_logs,
    purchase,
    replenishment,
    roles,
    system,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(master.router)
api_router.include_router(purchase.router)
api_router.include_router(inventory.router)
api_router.include_router(inventory_ops.router)
api_router.include_router(ledger.router)
api_router.include_router(forecast.router)
api_router.include_router(replenishment.router)
api_router.include_router(operation_logs.router)
api_router.include_router(system.router)
