"""Database table initialization script."""

from app.config import settings
from app.database import Base, engine
# Import all models to register them on Base.metadata
from app.models.event import Event  # noqa: F401


def init_db() -> None:
    """Create all database tables using the canonical Base and engine.

    This function is idempotent and safe to run multiple times.
    Existing tables and data are preserved without error.
    """
    Base.metadata.create_all(bind=engine)
    table_names = list(Base.metadata.tables.keys())
    print(f"Database initialized successfully at: {settings.database_url}")
    print(f"Registered tables: {', '.join(table_names)}")


if __name__ == "__main__":
    init_db()
