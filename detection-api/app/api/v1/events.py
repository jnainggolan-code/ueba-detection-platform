"""API v1 event endpoints — ingestion and query."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
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
    """Ingest a single event with anomaly detection pipeline."""
    service = EventService(session)
    return await service.ingest_single(payload, source="api")


@router.post("/batch", response_model=BatchEventResponse, status_code=201)
async def post_events_batch(
    payload: BatchEventCreate,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Ingest a batch of events (max 1000)."""
    service = EventService(session)
    return await service.ingest_batch(payload, source="api")


@router.get("", response_model=dict)
async def list_events(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    source: Optional[str] = None,
    entity: Optional[str] = None,
    event_type: Optional[str] = None,
    search: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """List events with pagination and filters."""
    service = EventService(session)
    return await service.list_events(
        page=page, limit=limit,
        source=source, entity=entity,
        event_type=event_type, search=search,
    )


@router.get("/{event_id}", response_model=dict)
async def get_event(
    event_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get a single event by ID."""
    service = EventService(session)
    return await service.get_event_by_id(event_id)
