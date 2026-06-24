"""API v2 process endpoint — enriched/annotated data."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.services.event_service import EventService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2", tags=["Process v2"])


@router.post("/process", status_code=201)
async def post_process_v2(
    payload: dict,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Ingest enriched/annotated data.

    Accepts pre-processed payloads with parsed_data populated.
    """
    service = EventService(session)
    return await service.ingest_processed(payload, source="process")
