"""Database module shim.

Re-exports canonical database session and engine objects from app.database
to maintain consistency and prevent duplicate engines or session factories.
"""

from app.database import Base, SessionLocal, connect_args, engine, get_db

__all__ = ["Base", "SessionLocal", "connect_args", "engine", "get_db"]
