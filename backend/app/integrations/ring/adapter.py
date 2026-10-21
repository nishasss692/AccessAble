"""Adapter for probing and reporting Ring integration connection state."""

from typing import Any, Optional

from app.models.source_connection import SourceConnection, utc_now
from app.repositories.connection_repository import ConnectionRepository


class RingAdapter:
    """Manages Ring integration status checks and connection state reporting.

    Does not falsely report a connected state without verified credentials and active sync.
    Defaults safely to 'unknown' with diagnostic details indicating pending hardware verification.
    """

    def __init__(
        self,
        forced_status: Optional[str] = None,
        forced_details: Optional[dict[str, Any]] = None,
        forced_error: Optional[str] = None,
    ) -> None:
        self.forced_status = forced_status
        self.forced_details = forced_details
        self.forced_error = forced_error

    def probe_status(self) -> dict[str, Any]:
        """Probe the current Ring connection state.

        Returns safe diagnostics without exposing secrets, credentials, or internal URLs.
        """
        if self.forced_status is not None:
            return {
                "status": self.forced_status,
                "is_connected": self.forced_status == "connected",
                "details": self.forced_details or {"mode": self.forced_status},
                "error_message": self.forced_error or ("Connection refused by upstream" if self.forced_status == "error" else None),
            }

        # Safe production/MVP default: Ring integration is not yet connected or verified
        return {
            "status": "unknown",
            "is_connected": False,
            "details": {
                "mode": "unconfigured",
                "note": "Live Ring credentials not configured. Integration mechanism pending hardware verification by Rishi.",
                "demo_events_supported": True,
            },
            "error_message": None,
        }

    def get_or_sync_status(self, repo: ConnectionRepository) -> SourceConnection:
        """Fetch current connection status record or probe and persist the initial status."""
        record = repo.get_by_source("ring")

        if record is None or self.forced_status is not None:
            probed = self.probe_status()
            record = repo.upsert_connection_status(
                source="ring",
                status=probed["status"],
                is_connected=probed["is_connected"],
                last_checked_at=utc_now(),
                error_message=probed.get("error_message"),
                details=probed.get("details", {}),
            )
        return record
