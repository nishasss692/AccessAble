"""Adapter for probing and reporting Ring integration connection state."""

from typing import Any, Optional

from app.models.source_connection import SourceConnection, utc_now
from app.repositories.connection_repository import ConnectionRepository
from app.config import settings


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
                "mode": "webhook",
                "environment": settings.ring_environment,
                "client_id_configured": bool(settings.ring_client_id),
                "client_secret_configured": bool(settings.ring_client_secret),
                "webhook_signature_configured": bool(settings.ring_hmac_signing_key),
                "webhook_receiver_enabled": bool(settings.ring_hmac_signing_key),
                "account_linking_configured": False,
                "account_link_verified": False,
                "demo_events_supported": True,
            },
            "error_message": None,
        }

    def get_or_sync_status(self, repo: ConnectionRepository) -> SourceConnection:
        """Fetch current connection status record or probe and persist the initial status."""
        record = repo.get_by_source("ring")

        probed = self.probe_status()
        record = repo.upsert_connection_status(
            source="ring",
            status=probed["status"],
            is_connected=probed["is_connected"],
            last_checked_at=utc_now(),
            last_successful_sync_at=(
                record.last_successful_sync_at if record is not None else None
            ),
            error_message=probed.get("error_message"),
            details=probed.get("details", {}),
        )
        return record
