"""Central API router aggregating versioned endpoint routers."""

from fastapi import APIRouter
from app.api.v1 import events, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(events.router)
