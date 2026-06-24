"""API v1 alerts endpoint — list and filter anomaly detections."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import get_db_session
from app.models.event import Base

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])


class AnomalyDetection(Base):
    """Anomaly detection results table."""

    __tablename__ = "anomaly_detections"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[Optional[int]]
    anomaly_type: Mapped[str]
    severity: Mapped[str]
    score: Mapped[float]
    z_score: Mapped[Optional[float]]
    description: Mapped[Optional[str]]
    evidence: Mapped[Optional[dict]]
    mitre_technique: Mapped[Optional[str]]
    mitre_tactic: Mapped[Optional[str]]
    status: Mapped[str] = mapped_column(default="open")
    assigned_to: Mapped[Optional[str]]
    time: Mapped[str]


class Entity(Base):
    """Entity table for joining entity_value."""

    __tablename__ = "entities"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_value: Mapped[str]
    entity_type: Mapped[str]


@router.get("/alerts")
async def list_alerts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    severity: Optional[str] = None,
    status: Optional[str] = None,
    entity: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """List anomaly detection alerts with pagination and filters.

    Supports filtering by severity, status, and entity name.
    """
    # Base query with join to get entity name
    query = (
        select(
            AnomalyDetection.id,
            AnomalyDetection.time,
            AnomalyDetection.anomaly_type,
            AnomalyDetection.severity,
            AnomalyDetection.score,
            AnomalyDetection.z_score,
            AnomalyDetection.description,
            AnomalyDetection.evidence,
            AnomalyDetection.mitre_technique,
            AnomalyDetection.mitre_tactic,
            AnomalyDetection.status,
            AnomalyDetection.assigned_to,
            AnomalyDetection.entity_id,
            Entity.entity_value,
        )
        .outerjoin(Entity, AnomalyDetection.entity_id == Entity.id)
        .order_by(AnomalyDetection.time.desc())
    )

    # Apply filters
    if severity:
        query = query.where(AnomalyDetection.severity == severity)
    if status:
        query = query.where(AnomalyDetection.status == status)
    if entity:
        query = query.where(Entity.entity_value == entity)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    rows = result.all()

    alerts = []
    for row in rows:
        # Build severity label mapping
        severity_label = row.severity
        risk_score = _severity_to_risk(row.severity, row.score)

        # Build title from description or anomaly type
        if row.description:
            title = row.description
            if len(title) > 100:
                title = title[:100] + "..."
        else:
            title = f"{row.anomaly_type.replace('_', ' ').title()} — {row.entity_value or 'unknown'}"

        alerts.append({
            "id": f"ALT-{row.id}",
            "title": title,
            "description": row.description or "",
            "severity": severity_label,
            "status": row.status,
            "assignee": row.assigned_to,
            "entity": row.entity_value or "unknown",
            "risk_score": risk_score,
            "created_at": row.time,
            "updated_at": row.time,
            "events": [],
        })

    return {
        "data": alerts,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": max(1, (total + limit - 1) // limit),
    }


def _severity_to_risk(severity: str, score: float) -> int:
    """Map severity + score to a 0-100 risk score."""
    base = {
        "critical": 85,
        "high": 65,
        "medium": 40,
        "low": 20,
        "info": 5,
    }.get(severity, 25)
    # Blend with normalized score (0-1) * remaining range
    score_norm = min(1.0, max(0.0, score / 100.0)) if score else 0.5
    risk = base + int(score_norm * (100 - base))
    return min(100, max(0, risk))
