"""API routes for accessibility preferences."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_preference_service
from app.schemas.preferences import PreferencesResponse, PreferencesUpdate
from app.services.preference_service import PreferenceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preferences", tags=["Preferences"])


@router.get(
    "",
    response_model=PreferencesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get accessibility preferences",
    description="Retrieve the current accessibility preferences. If none exist yet, default settings are persisted and returned.",
)
def get_preferences(
    service: PreferenceService = Depends(get_preference_service),
) -> PreferencesResponse:
    """Retrieve currently active accessibility preferences."""
    try:
        pref = service.get_preferences()
        return PreferencesResponse.model_validate(pref)
    except Exception as exc:
        logger.exception("Unexpected error fetching preferences: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving preferences.",
        ) from exc


@router.put(
    "",
    response_model=PreferencesResponse,
    status_code=status.HTTP_200_OK,
    summary="Update accessibility preferences",
    description="Update and persist accessibility preferences. Updates the existing preference profile rather than creating duplicate records.",
    responses={
        200: {"description": "Preferences successfully updated."},
        422: {"description": "Validation error in preference fields."},
        500: {"description": "Internal server error."},
    },
)
def update_preferences(
    prefs_in: PreferencesUpdate,
    service: PreferenceService = Depends(get_preference_service),
) -> PreferencesResponse:
    """Update accessibility preferences."""
    try:
        updated = service.update_preferences(prefs_in)
        return PreferencesResponse.model_validate(updated)
    except Exception as exc:
        logger.exception("Unexpected error updating preferences: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating preferences.",
        ) from exc
