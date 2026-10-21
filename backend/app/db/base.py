"""Database Base and model registry.

Re-exports the canonical Declarative Base from app.database and imports
all SQLAlchemy models so they are registered with Base.metadata.
"""

from app.database import Base
from app.models.acknowledgement import Acknowledgement
from app.models.event import Event
from app.models.source_connection import SourceConnection
from app.models.user_preferences import UserPreference

__all__ = ["Base", "Event", "UserPreference", "Acknowledgement", "SourceConnection"]
