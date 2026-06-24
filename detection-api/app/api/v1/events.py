"""API v1 event endpoints — single and batch event ingestion."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.event import (
    EventCreate,
    BatchEventCreate,
    EventResponse,
    BatchEventResponse,
)
from app.services.event_service import EventService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/events", tags=["Events v1"])


@router.post("", response_model=EventResponse, status_code=201)
async def post_event(
    payload: EventCreate,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Ingest a single event.

    Validates the payload via Pydantic and inserts into logs_raw.
    """
    service = EventService(session)
    return await service.ingest_single(payload, source="api")


@router.post("/batch", response_model=BatchEventResponse, status_code=201)
async def post_events_batch(
    payload: BatchEventCreate,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Ingest a batch of events (max 1000).

    Validates all events and performs a bulk insert.
    """
    service = EventService(session)
    return await service.ingest_batch(payload, source="api")
