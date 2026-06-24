"""API v1 health check and stats endpoints."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import check_db_connection, get_db_session
from app.schemas.health import HealthResponse, StatsResponse
from app.services.event_service import EventService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Health & Stats"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> dict:
    """Health check endpoint. Pings the database and returns status."""
    db_status = await check_db_connection()
    return {
        "status": "ok",
        "module": "UEBA",
        "version": settings.app_version,
        "db_connected": db_status.get("db_connected", False),
    }


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return aggregate event statistics.

    Includes total event count, breakdown by source, and by entity.
    """
    service = EventService(session)
    return await service.get_stats()
