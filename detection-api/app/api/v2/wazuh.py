"""API v2 Wazuh endpoint — Wazuh-native alert format."""

import hashlib
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.services.event_service import EventService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2", tags=["Wazuh v2"])


@router.post("/wazuh", status_code=201)
async def post_wazuh_v2(
    payload: dict,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Ingest Wazuh-native alert format with anomaly detection pipeline."""
    # 1. Compute SHA256 hash from sorted JSON payload
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

    # 3. If duplicate, skip with log + return 200 (not error)
    if count > 0:
        logger.info(
            "Duplicate alert detected with hash %s, skipping ingestion.",
            sha256_hash,
        )
        return JSONResponse(
            status_code=200,
            content={
                "status": "duplicate_skipped",
                "detail": "Duplicate alert, skipped",
            },
        )

    # 4. Inject hash into payload before insert for future dedup
    payload["sha256_hash"] = sha256_hash

    service = EventService(session)
    return await service.ingest_wazuh(payload, source="wazuh")
