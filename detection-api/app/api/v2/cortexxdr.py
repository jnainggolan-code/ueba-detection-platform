"""API v2 Cortex XDR endpoint — webhook receiver for Palo Alto Cortex XDR."""

import hashlib
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db_session
from app.services.event_service import EventService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2", tags=["Cortex XDR v2"])


def verify_cortex_xdr_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """Validate the x-api-key header against configured Cortex XDR keys.

    If cortex_xdr_api_keys is empty, auth is bypassed (open endpoint).
    Otherwise, the provided key must match one of the comma-separated values.
    """
    configured = settings.cortex_xdr_api_keys
    if not configured:
        return

    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing x-api-key header")

    valid_keys = [k.strip() for k in configured.split(",") if k.strip()]
    if x_api_key not in valid_keys:
        raise HTTPException(status_code=403, detail="Invalid API key")


@router.post("/cortexxdr", status_code=201)
async def post_cortex_xdr_v2(
    payload: dict,
    _: None = Depends(verify_cortex_xdr_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Ingest Cortex XDR alert/webhook events with anomaly detection pipeline.

    Accepts JSON payload from Palo Alto Cortex XDR SIEM/webhook integrations.
    Stores the raw payload as-is and enqueues it for parsing, anomaly detection,
    and risk scoring.

    Common Cortex XDR event types:
      - XDR incident alerts
      - BIOC (Behavioral IOC) alerts
      - Correlation alerts
      - Endpoint malware detections
    """
    # 1. Compute SHA256 hash from sorted JSON payload for dedup
    payload_str = json.dumps(payload, sort_keys=True)
    sha256_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    # 2. Check for duplicate in logs_raw within the last 5 minutes
    query = text(
        "SELECT COUNT(*) FROM logs_raw "
        "WHERE raw_payload->>'sha256_hash' = :hash "
        "AND ingested_at > NOW() - INTERVAL '5 minutes'"
    )
    result = await session.execute(query, {"hash": sha256_hash})
    count = result.scalar() or 0

    # 3. If duplicate, skip
    if count > 0:
        logger.info("Duplicate Cortex XDR event detected, hash=%s, skipping.", sha256_hash)
        return JSONResponse(
            status_code=200,
            content={"status": "duplicate_skipped", "detail": "Duplicate event, skipped"},
        )

    # 4. Inject hash into payload before insert
    payload["sha256_hash"] = sha256_hash

    service = EventService(session)
    return await service.ingest_raw(payload, source="cortex_xdr")


@router.get("/cortexxdr", status_code=200)
async def get_cortex_xdr_health() -> dict:
    """Health check for the Cortex XDR webhook endpoint."""
    return {"service": "cortex-xdr-webhook", "status": "ready", "version": "2.0"}
