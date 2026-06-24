"""API v2 ingestion endpoints — source-agnostic raw data."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.services.event_service import EventService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2", tags=["Ingest v2"])


@router.post("/ingest", status_code=201)
async def post_ingest_v2(
    payload: dict,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Ingest raw data (source-agnostic) with anomaly detection pipeline."""
    service = EventService(session)
    return await service.ingest_raw(
        payload, source="raw",
        background_tasks=background_tasks,
    )
