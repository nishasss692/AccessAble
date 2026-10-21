"""Service layer for accessibility preference management."""

import logging
from app.models.user_preferences import UserPreference
from app.repositories.preferences_repository import PreferencesRepository
from app.schemas.preferences import PreferencesUpdate

logger = logging.getLogger(__name__)

# Documented sensible defaults for initial setup
DEFAULT_VISUAL_ALERTS_ENABLED = True
DEFAULT_AUDIO_ALERTS_ENABLED = True
DEFAULT_HIGH_CONTRAST_ENABLED = False
DEFAULT_TEXT_SCALE = "medium"


class PreferenceService:
    """Service coordinating reading and updating accessibility preferences."""

    def __init__(self, repository: PreferencesRepository) -> None:
        self.repository = repository

    def get_preferences(self, profile_name: str = "default") -> UserPreference:
        """Retrieve the current preferences for a profile.

        If no preference record exists yet, the documented defaults are persisted
        and returned to ensure consistent state across subsequent requests.
        """
        pref = self.repository.get_by_profile(profile_name)
        if pref is None:
            logger.info("No preferences found for profile '%s'. Persisting initial defaults.", profile_name)
            pref = self.repository.create_or_update(
                visual_alerts_enabled=DEFAULT_VISUAL_ALERTS_ENABLED,
                audio_alerts_enabled=DEFAULT_AUDIO_ALERTS_ENABLED,
                high_contrast_enabled=DEFAULT_HIGH_CONTRAST_ENABLED,
                text_scale=DEFAULT_TEXT_SCALE,
                profile_name=profile_name,
            )
        return pref

    def update_preferences(
        self,
        prefs_in: PreferencesUpdate,
        profile_name: str = "default",
    ) -> UserPreference:
        """Update and persist preferences for the specified profile."""
        return self.repository.create_or_update(
            visual_alerts_enabled=prefs_in.visual_alerts_enabled,
            audio_alerts_enabled=prefs_in.audio_alerts_enabled,
            high_contrast_enabled=prefs_in.high_contrast_enabled,
            text_scale=prefs_in.text_scale,
            profile_name=profile_name,
        )
