"""Central API router aggregating versioned endpoint routers."""

from fastapi import APIRouter
from app.api.v1 import acknowledgements, events, health, integrations, preferences, ring_webhook

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(events.router)
api_router.include_router(preferences.router)
api_router.include_router(acknowledgements.router)
api_router.include_router(integrations.router)
api_router.include_router(ring_webhook.router)
