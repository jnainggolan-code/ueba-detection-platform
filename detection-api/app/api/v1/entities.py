"""API v1 entities endpoint — entity detail and risk profile."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import get_db_session
from app.models.event import Base, LogsRaw

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/entities", tags=["Entities"])


class Entity(Base):
    """Entity table — mirrors detection-db schema."""

    __tablename__ = "entities"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_type: Mapped[str]
    entity_value: Mapped[str]
    first_seen: Mapped[Optional[str]]
    last_seen: Mapped[Optional[str]]
    profile_metadata: Mapped[Optional[dict]]
    risk_score: Mapped[float] = mapped_column(default=0.0)
    risk_level: Mapped[str] = mapped_column(default="low")
    risk_factors: Mapped[Optional[dict]]
    tags: Mapped[Optional[list]]


class AnomalyDetection(Base):
    """Anomaly detection results table."""

    __tablename__ = "anomaly_detections"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[Optional[int]]
    anomaly_type: Mapped[str]
    severity: Mapped[str]
    score: Mapped[float]
    description: Mapped[Optional[str]]
    status: Mapped[str] = mapped_column(default="open")
    time: Mapped[str]


@router.get("/{entity_value}")
async def get_entity_detail(
    entity_value: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return detailed profile for a single entity.

    Includes risk score, recent events, anomalies, and metadata.
    """
    # Look up entity by entity_value
    result = await session.execute(
        select(Entity).where(Entity.entity_value == entity_value)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(
            status_code=404,
            detail=f"Entity '{entity_value}' not found",
        )

    # Risk score (prefer DB value, fallback to risk_scores table)
    risk_score = entity.risk_score

    # Recent events (10 latest for this entity)
    # Try matching via parsed_data->>'entity_id' or entity FK
    events_result = await session.execute(
        select(LogsRaw)
        .where(LogsRaw.parsed_data["entity_id"].as_string() == entity_value)
        .order_by(LogsRaw.time.desc())
        .limit(10)
    )
    recent_events_raw = list(events_result.scalars().all())

    # If no results from parsed_data, try raw_payload matching
    if not recent_events_raw:
        events_result = await session.execute(
            select(LogsRaw)
            .where(LogsRaw.raw_payload["entity_id"].as_string() == entity_value)
            .order_by(LogsRaw.time.desc())
            .limit(10)
        )
        recent_events_raw = list(events_result.scalars().all())

    # Anomalies for this entity
    anomalies_result = await session.execute(
        select(AnomalyDetection)
        .where(AnomalyDetection.entity_id == entity.id)
        .order_by(AnomalyDetection.time.desc())
        .limit(20)
    )
    anomalies_raw = list(anomalies_result.scalars().all())

    # Build department from profile_metadata
    department = "Unknown"
    if entity.profile_metadata and isinstance(entity.profile_metadata, dict):
        department = entity.profile_metadata.get(
            "department",
            entity.profile_metadata.get("group", "Unknown"),
        )

    return {
        "entity": entity.entity_value,
        "risk_score": risk_score,
        "risk_level": entity.risk_level,
        "department": department,
        "first_seen": entity.first_seen,
        "last_seen": entity.last_seen,
        "tags": entity.tags or [],
        "recent_events": [
            {
                "id": str(e.id),
                "timestamp": e.time.isoformat() if e.time else None,
                "source": e.source,
                "log_level": e.log_level,
                "event_type": (
                    e.parsed_data.get("event_type", "unknown")
                    if e.parsed_data else "unknown"
                ),
                "risk_score": _calc_risk(e.log_level),
                "details": e.raw_payload if e.raw_payload else {},
            }
            for e in recent_events_raw
        ],
        "anomalies": [
            {
                "id": str(a.id),
                "anomaly_type": a.anomaly_type,
                "severity": a.severity,
                "score": a.score,
                "description": a.description,
                "status": a.status,
                "timestamp": a.time,
            }
            for a in anomalies_raw
        ],
    }


def _calc_risk(log_level: str | None) -> int:
    _map = {"info": 10, "warning": 30, "error": 60, "critical": 90}
    return _map.get(log_level or "info", 25)
