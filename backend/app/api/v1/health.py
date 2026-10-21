"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health check")
def health():
    """Return backend health status."""
    return {
        "status": "ok",
        "service": "accessable-api",
    }
