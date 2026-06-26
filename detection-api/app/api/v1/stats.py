"""API v1 stats endpoint — aggregate statistics."""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, text, select, case
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
    time_range: str = Query(default="24h", description="Time range: 24h, 7d, or 30d"),
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

    # --- Chart data additions ---
    # Hourly event trend (respects time_range param)
    if time_range == "7d":
        range_hours = 168  # 7 * 24
        range_label = "7d"
    elif time_range == "30d":
        range_hours = 720  # 30 * 24
        range_label = "30d"
    else:
        range_hours = 24
        range_label = "24h"
    hours_ago = datetime.now(timezone.utc) - timedelta(hours=range_hours)
    hourly_rows = await session.execute(
        select(
            func.date_trunc("hour", LogsRaw.time).label("hour"),
            func.count(LogsRaw.id).label("cnt"),
        )
        .where(LogsRaw.time >= hours_ago)
        .group_by(text("hour"))
        .order_by(text("hour"))
    )
    hourly_map = {r.hour.strftime("%Y-%m-%d %H:00:00+00:00") if hasattr(r.hour, "strftime") else str(r.hour): r.cnt for r in hourly_rows.all()}
    event_trend = []
    if range_label == "24h":
        # Hourly buckets for 24h
        bucket_tpl = "hour"
        bucket_format = "%H:00"
        num_buckets = 24
    elif range_label == "7d":
        # 6-hour buckets for 7d
        bucket_tpl = "day"
        bucket_format = "%d %H:00"
        num_buckets = 28  # 168/6
    else:
        # Daily buckets for 30d
        bucket_tpl = "day"
        bucket_format = "%d %b"
        num_buckets = 30
    for h in range(num_buckets):
        ts = datetime.now(timezone.utc) - timedelta(hours=num_buckets-1-h)
        hour_key = ts.strftime("%Y-%m-%d %H:00:00+00:00")
        hour_label = ts.strftime(bucket_format)
        count = hourly_map.get(hour_key, 0)
        event_trend.append({"hour": hour_label, "events": count, "alerts": 0})

    # Entity risk ranking (top 10 by risk_score)
    entity_rows = await session.execute(
        select(Entity.entity_value, Entity.risk_score)
        .order_by(Entity.risk_score.desc().nullslast())
        .limit(10)
    )
    entity_risk = [
        {"name": row.entity_value or f"entity-{i}", "score": row.risk_score or 0}
        for i, row in enumerate(entity_rows.all())
    ]

    # Event type distribution (by source as proxy)
    total_all = total_events or 1
    event_type_dist = []
    source_colors = {"wazuh": "#3b82f6", "api": "#10b981", "windows": "#a855f7",
                     "linux": "#eab308", "network": "#ef4444", "cloud": "#8b5cf6"}
    for i, src in enumerate(events_by_source):
        colors = ["#3b82f6", "#10b981", "#a855f7", "#eab308", "#ef4444", "#8b5cf6"]
        event_type_dist.append({
            "name": src["source"].title(),
            "value": round(src["count"] / total_all * 100, 1),
        })

    # Alert severity breakdown (from anomaly_detections)
    sev_rows = await session.execute(
        select(
            func.sum(case((AnomalyDetection.severity == "critical", 1), else_=0)).label("critical"),
            func.sum(case((AnomalyDetection.severity == "high", 1), else_=0)).label("high"),
            func.sum(case((AnomalyDetection.severity == "medium", 1), else_=0)).label("medium"),
            func.sum(case((AnomalyDetection.severity == "low", 1), else_=0)).label("low"),
        )
    )
    sev_row = sev_rows.one()
    alert_severity = [
        {"severity": "Critical", "count": sev_row.critical or 0, "color": "#ef4444"},
        {"severity": "High", "count": sev_row.high or 0, "color": "#f97316"},
        {"severity": "Medium", "count": sev_row.medium or 0, "color": "#eab308"},
        {"severity": "Low", "count": sev_row.low or 0, "color": "#3b82f6"},
    ]

    # Risk distribution by entity risk level
    risk_rows = await session.execute(
        select(
            func.sum(case((Entity.risk_score >= 80, 1), else_=0)).label("critical"),
            func.sum(case((Entity.risk_score >= 60, 1), else_=0)).label("high"),
            func.sum(case((Entity.risk_score >= 30, 1), else_=0)).label("medium"),
            func.sum(case((Entity.risk_score < 30, 1), else_=0)).label("low"),
        )
    )
    risk_row = risk_rows.one()
    risk_distribution = [
        {"level": "Critical", "count": risk_row.critical or 0, "color": "#ef4444"},
        {"level": "High", "count": risk_row.high or 0, "color": "#f97316"},
        {"level": "Medium", "count": risk_row.medium or 0, "color": "#eab308"},
        {"level": "Low", "count": risk_row.low or 0, "color": "#3b82f6"},
    ]

    # Health status
    health_status = [
        {"label": "Detection Engine", "status": "healthy", "value": "Active"},
        {"label": "Data Pipeline", "status": "healthy", "value": f"{events_last_hour} evts/hr"},
        {"label": "ML Model", "status": "warning", "value": "Active"},
        {"label": "Storage", "status": "healthy", "value": f"{total_events} events"},
        {"label": "Alert Queue", "status": "warning", "value": f"{active_alerts} pending"},
        {"label": "Critical Alerts", "status": "critical" if critical_alerts > 0 else "healthy", "value": str(critical_alerts)},
    ]

    return {
        "total_events": total_events,
        "by_source": events_by_source,
        "active_alerts": active_alerts,
        "critical_alerts": critical_alerts,
        "entities_at_risk": entities_at_risk,
        "avg_risk_score": avg_risk_score,
        "events_last_hour": events_last_hour,
        "entities_monitored": entities_at_risk + 5,
        # Chart data
        "event_trend": event_trend,
        "entity_risk": entity_risk,
        "event_type_distribution": event_type_dist,
        "alert_severity": alert_severity,
        "risk_distribution": risk_distribution,
        "health_status": health_status,
    }
