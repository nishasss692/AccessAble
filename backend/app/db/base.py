"""Database Base and model registry.

Re-exports the canonical Declarative Base from app.database and imports
all SQLAlchemy models so they are registered with Base.metadata.
"""

from app.database import Base
from app.models.event import Event

__all__ = ["Base", "Event"]
