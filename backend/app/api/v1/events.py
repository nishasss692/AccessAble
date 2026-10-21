"""API routes for event ingestion and listing."""

from datetime import datetime
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.dependencies import get_event_ingestion_service, get_event_repository
from app.repositories.event_repository import EventRepository
from app.schemas.event import (
    EventCreate,
    EventIngestionResponse,
    EventListResponse,
    EventResponse,
    normalize_to_utc,
)
from app.services.event_ingestion_service import EventIngestionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["Events"])


@router.post(
    "",
    response_model=EventIngestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest an accessibility event",
    description=(
        "Ingests a normalized event. If an event with the same source and external_event_id "
        "already exists, returns HTTP 200 with the existing record and is_duplicate=True. "
        "Otherwise, persists the new event and returns HTTP 201 with is_duplicate=False."
    ),
    responses={
        201: {"description": "New event successfully ingested and persisted."},
        200: {"description": "Duplicate event detected; existing record returned."},
        422: {"description": "Validation error in request payload."},
        500: {"description": "Internal server error."},
    },
)
def create_event(
    event_in: EventCreate,
    response: Response,
    ingestion_service: EventIngestionService = Depends(get_event_ingestion_service),
) -> EventIngestionResponse:
    """Ingest a validated event with duplicate detection."""
    try:
        result = ingestion_service.ingest_event(event_in)

        # Set status code dynamically: 200 for duplicates, 201 for newly created
        if result.is_duplicate:
            response.status_code = status.HTTP_200_OK
        else:
            response.status_code = status.HTTP_201_CREATED

        return EventIngestionResponse(
            event=EventResponse.model_validate(result.event),
            is_duplicate=result.is_duplicate,
        )
    except Exception as exc:
        logger.exception("Unexpected error while ingesting event: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the event.",
        ) from exc


@router.get(
    "",
    response_model=EventListResponse,
    status_code=status.HTTP_200_OK,
    summary="List accessibility events",
    description="Retrieve paginated accessibility events with optional filtering by source, event type, and occurred_at time window.",
    responses={
        200: {"description": "Paginated list of events matching query criteria."},
        400: {"description": "Invalid query parameters (e.g., start_time after end_time)."},
        422: {"description": "Validation error in query parameters."},
    },
)
def list_events(
    source: Optional[str] = Query(None, description="Exact source to filter by (e.g., 'ring', 'demo')"),
    event_type: Optional[str] = Query(None, description="Exact event type to filter by (e.g., 'motion')"),
    start_time: Optional[datetime] = Query(None, description="Inclusive lower bound timestamp for occurred_at"),
    end_time: Optional[datetime] = Query(None, description="Inclusive upper bound timestamp for occurred_at"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of events to return (1-100)"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    repo: EventRepository = Depends(get_event_repository),
) -> EventListResponse:
    """List events with filtering, pagination, and deterministic ordering."""
    if start_time and end_time:
        norm_start = normalize_to_utc(start_time)
        norm_end = normalize_to_utc(end_time)
        if norm_start > norm_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time cannot be later than end_time",
            )
        start_time = norm_start
        end_time = norm_end
    elif start_time:
        start_time = normalize_to_utc(start_time)
    elif end_time:
        end_time = normalize_to_utc(end_time)

    events, total = repo.list_events(
        source=source.strip().lower() if source else None,
        event_type=event_type.strip().lower() if event_type else None,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )

    return EventListResponse(
        items=[EventResponse.model_validate(e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
    )
