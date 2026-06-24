"""API v2 Wazuh endpoint — Wazuh-native alert format."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.services.event_service import EventService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2", tags=["Wazuh v2"])


@router.post("/wazuh", status_code=201)
async def post_wazuh_v2(
    payload: dict,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Ingest Wazuh-native alert format with anomaly detection pipeline."""
    service = EventService(session)
    return await service.ingest_wazuh(
        payload, source="wazuh",
        background_tasks=background_tasks,
    )
