"""Repository for accessibility preferences persistence and querying."""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.user_preferences import UserPreference, utc_now


class PreferencesRepository:
    """Repository handling database operations for UserPreference records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_profile(self, profile_name: str = "default") -> Optional[UserPreference]:
        """Fetch preference record by profile name."""
        stmt = select(UserPreference).where(UserPreference.profile_name == profile_name)
        return self.db.scalar(stmt)

    def create_or_update(
        self,
        visual_alerts_enabled: bool,
        audio_alerts_enabled: bool,
        high_contrast_enabled: bool,
        text_scale: str,
        profile_name: str = "default",
    ) -> UserPreference:
        """Create or update user preferences for a given profile."""
        try:
            pref = self.get_by_profile(profile_name)
            if pref is None:
                pref = UserPreference(
                    profile_name=profile_name,
                    visual_alerts_enabled=visual_alerts_enabled,
                    audio_alerts_enabled=audio_alerts_enabled,
                    high_contrast_enabled=high_contrast_enabled,
                    text_scale=text_scale,
                    updated_at=utc_now(),
                )
                self.db.add(pref)
            else:
                pref.visual_alerts_enabled = visual_alerts_enabled
                pref.audio_alerts_enabled = audio_alerts_enabled
                pref.high_contrast_enabled = high_contrast_enabled
                pref.text_scale = text_scale
                pref.updated_at = utc_now()

            self.db.commit()
            self.db.refresh(pref)
            return pref
        except SQLAlchemyError:
            self.db.rollback()
            raise
