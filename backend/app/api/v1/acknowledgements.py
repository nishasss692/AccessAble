"""API routes for event acknowledgements and history."""

import logging
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_acknowledgement_service
from app.schemas.acknowledgement import (
    AcknowledgementCreate,
    AcknowledgementListResponse,
    AcknowledgementResponse,
)
from app.services.acknowledgement_service import (
    AcknowledgementService,
    DuplicateAcknowledgementError,
    EventNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/acknowledgements", tags=["Acknowledgements"])


@router.post(
    "",
    response_model=AcknowledgementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Acknowledge or dismiss an event",
    description=(
        "Records an acknowledgement action for an event. Verifies the event exists "
        "and prevents unintended duplicate operations if the event is already in the requested state."
    ),
    responses={
        201: {"description": "Acknowledgement successfully recorded."},
        404: {"description": "Referenced event does not exist."},
        409: {"description": "Duplicate acknowledgement operation."},
        422: {"description": "Validation error in request payload."},
        500: {"description": "Internal server error."},
    },
)
def create_acknowledgement(
    ack_in: AcknowledgementCreate,
    service: AcknowledgementService = Depends(get_acknowledgement_service),
) -> AcknowledgementResponse:
    """Record an acknowledgement or dismissal for an event."""
    try:
        ack = service.create_acknowledgement(ack_in)
        return AcknowledgementResponse.model_validate(ack)
    except EventNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err
    except DuplicateAcknowledgementError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(err),
        ) from err
    except Exception as exc:
        logger.exception("Unexpected error creating acknowledgement: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the acknowledgement.",
        ) from exc


@router.get(
    "",
    response_model=AcknowledgementListResponse,
    status_code=status.HTTP_200_OK,
    summary="List acknowledgement history",
    description="Retrieve paginated history of event acknowledgements, with optional filters for event_id and action.",
    responses={
        200: {"description": "Paginated history list of acknowledgements."},
        422: {"description": "Validation error in query parameters."},
    },
)
def list_acknowledgements(
    event_id: Optional[int] = Query(None, gt=0, description="Filter history by event ID"),
    action: Optional[Literal["acknowledged", "dismissed"]] = Query(
        None,
        description="Filter history by action: 'acknowledged' or 'dismissed'",
    ),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of items to return (1-100)"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    service: AcknowledgementService = Depends(get_acknowledgement_service),
) -> AcknowledgementListResponse:
    """Retrieve acknowledgement history with filtering and pagination."""
    items, total = service.list_acknowledgements(
        event_id=event_id,
        action=action,
        limit=limit,
        offset=offset,
    )
    return AcknowledgementListResponse(
        items=[AcknowledgementResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )
