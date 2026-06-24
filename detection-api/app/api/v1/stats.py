"""API v1 stats endpoint — aggregate statistics."""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import BIGINT

from app.db.session import get_db_session
from app.models.event import Base, LogsRaw

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Stats"])


class Entity(Base):
    """Entity/entity table — mirrors detection-db schema."""

    __tablename__ = "entities"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_value: Mapped[str]
    entity_type: Mapped[str]
    risk_score: Mapped[float] = mapped_column(default=0.0)
    risk_level: Mapped[str] = mapped_column(default="low")


class AnomalyDetection(Base):
    """Anomaly detection results table."""

    __tablename__ = "anomaly_detections"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    severity: Mapped[str]
    status: Mapped[str] = mapped_column(default="open")


@router.get("/stats")
async def get_stats(
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return aggregate platform statistics."""
    # Total events
    total = await session.execute(select(func.count(LogsRaw.id)))
    total_events = total.scalar() or 0

    # Events by source
    rows = await session.execute(
        select(LogsRaw.source, func.count(LogsRaw.id).label("cnt"))
        .group_by(LogsRaw.source)
    )
    events_by_source = [
        {"source": row.source, "count": row.cnt} for row in rows.all()
    ]

    # Active alerts (open)
    active = await session.execute(
        select(func.count(AnomalyDetection.id))
        .where(AnomalyDetection.status == "open")
    )
    active_alerts = active.scalar() or 0

    # Critical alerts (open + critical)
    critical = await session.execute(
        select(func.count(AnomalyDetection.id))
        .where(AnomalyDetection.status == "open")
        .where(AnomalyDetection.severity == "critical")
    )
    critical_alerts = critical.scalar() or 0

    # Entities at risk (risk_score > 50)
    at_risk = await session.execute(
        select(func.count(Entity.id))
        .where(Entity.risk_score > 50)
    )
    entities_at_risk = at_risk.scalar() or 0

    # Average risk score
    avg = await session.execute(
        select(func.avg(Entity.risk_score))
    )
    avg_risk_score = round(avg.scalar() or 0, 1)

    # Events in last hour
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    last_hour = await session.execute(
        select(func.count(LogsRaw.id))
        .where(LogsRaw.time >= cutoff)
    )
    events_last_hour = last_hour.scalar() or 0

    logger.info(
        "Stats: total=%d sources=%d alerts=%d critical=%d at_risk=%d "
        "avg_score=%.1f last_hour=%d",
        total_events, len(events_by_source), active_alerts,
        critical_alerts, entities_at_risk, avg_risk_score,
        events_last_hour,
    )

    return {
        "total_events": total_events,
        "events_by_source": events_by_source,
        "active_alerts": active_alerts,
        "critical_alerts": critical_alerts,
        "entities_at_risk": entities_at_risk,
        "avg_risk_score": avg_risk_score,
        "events_last_hour": events_last_hour,
    }
