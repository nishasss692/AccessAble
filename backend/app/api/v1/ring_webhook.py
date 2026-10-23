"""Public Ring webhook receiver."""

import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import ValidationError

from app.config import settings
from app.dependencies import get_connection_repository, get_event_ingestion_service
from app.integrations.ring.webhook import normalize_webhook, verify_signature
from app.repositories.connection_repository import ConnectionRepository
from app.schemas.event import EventCreate
from app.services.event_ingestion_service import EventIngestionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations/ring", tags=["Ring Webhook"])


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def receive_ring_webhook(
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
    ingestion: EventIngestionService = Depends(get_event_ingestion_service),
    connection_repo: ConnectionRepository = Depends(get_connection_repository),
) -> dict[str, object]:
    """Verify raw-body HMAC, validate, and persist before acknowledging delivery."""
    signing_key = settings.ring_hmac_signing_key
    if not signing_key:
        raise HTTPException(status_code=503, detail="Ring webhook receiver is not configured")

    raw_body = await request.body()
    if not verify_signature(signing_key, raw_body, x_signature):
        raise HTTPException(status_code=401, detail="Invalid Ring webhook signature")

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Malformed Ring webhook JSON") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Malformed Ring webhook payload")

    try:
        normalized = normalize_webhook(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    if normalized is None:
        event_data = payload.get("data")
        ring_type = event_data.get("type") if isinstance(event_data, dict) else "unknown"
        logger.info("Ignored unsupported Ring webhook event type: %s", str(ring_type)[:80])
        return {"status": "ignored", "reason": "unsupported_event_type"}

    try:
        event = EventCreate.model_validate(normalized)
        result = ingestion.ingest_event(event)
        # Persist the latest receipt time for operational status. Event ingestion
        # already committed; failures here are retried safely via request_id.
        connection_repo.upsert_connection_status(
            source="ring",
            status="unknown",
            is_connected=False,
            last_successful_sync_at=result.event.received_at,
            details={
                "mode": "webhook",
                "environment": settings.ring_environment,
                "client_id_configured": bool(settings.ring_client_id),
                "client_secret_configured": bool(settings.ring_client_secret),
                "webhook_signature_configured": True,
                "webhook_receiver_enabled": True,
                "account_linking_configured": False,
                "account_link_verified": False,
                "demo_events_supported": True,
            },
        )
    except ValidationError:
        raise HTTPException(status_code=400, detail="Invalid normalized Ring event") from None
    except Exception:
        logger.error("Ring webhook persistence failed")
        raise HTTPException(status_code=503, detail="Ring webhook event could not be persisted") from None

    return {"status": "processed", "is_duplicate": result.is_duplicate}
