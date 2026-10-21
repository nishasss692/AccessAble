"""API routes for external device integrations and connection status."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_connection_repository, get_ring_adapter
from app.integrations.ring.adapter import RingAdapter
from app.repositories.connection_repository import ConnectionRepository
from app.schemas.ring import RingStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["Integrations"])


@router.get(
    "/ring/status",
    response_model=RingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Ring integration status",
    description=(
        "Retrieves the current connection state of the Ring integration. "
        "Possible states: 'connected', 'disconnected', 'error', 'unknown'. "
        "Reports 'unknown' when live Ring credentials have not been configured."
    ),
    responses={
        200: {"description": "Current Ring integration connection state."},
        500: {"description": "Internal server error while checking status."},
    },
)
def get_ring_status(
    adapter: RingAdapter = Depends(get_ring_adapter),
    repo: ConnectionRepository = Depends(get_connection_repository),
) -> RingStatusResponse:
    """Retrieve the current known connection status of the Ring integration."""
    try:
        record = adapter.get_or_sync_status(repo)
        return RingStatusResponse.model_validate(record)
    except Exception as exc:
        logger.exception("Unexpected error checking Ring integration status: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while checking integration status.",
        ) from exc
