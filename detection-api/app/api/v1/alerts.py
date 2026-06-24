"""API v1 alerts endpoint — list, filter, update anomaly detections."""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Column, DateTime
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
    evidence = Column(JSONB, nullable=True)
    mitre_technique: Mapped[Optional[str]]
    mitre_tactic: Mapped[Optional[str]]
    status: Mapped[str] = mapped_column(default="open")
    assigned_to: Mapped[Optional[str]]
    time = Column(DateTime(timezone=True), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[Optional[str]]


class Entity(Base):
    """Entity table for joining entity_value."""

    __tablename__ = "entities"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_value: Mapped[str]
    entity_type: Mapped[str]


# ── Valid status transitions ──
VALID_TRANSITIONS = {
    "open": {"investigating"},
    "investigating": {"resolved", "dismissed"},
    "resolved": set(),
    "dismissed": set(),
}

TERMINAL_STATUSES = {"resolved", "dismissed"}


@router.get("/counts")
async def get_alert_counts(
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return aggregate counts of alerts by status and severity."""
    # Total
    total_q = select(func.count(AnomalyDetection.id))
    total = (await session.execute(total_q)).scalar() or 0

    # By status
    open_q = select(func.count(AnomalyDetection.id)).where(AnomalyDetection.status == "open")
    open_count = (await session.execute(open_q)).scalar() or 0

    investigating_q = select(func.count(AnomalyDetection.id)).where(AnomalyDetection.status == "investigating")
    investigating_count = (await session.execute(investigating_q)).scalar() or 0

    resolved_q = select(func.count(AnomalyDetection.id)).where(AnomalyDetection.status == "resolved")
    resolved_count = (await session.execute(resolved_q)).scalar() or 0

    dismissed_q = select(func.count(AnomalyDetection.id)).where(AnomalyDetection.status == "dismissed")
    dismissed_count = (await session.execute(dismissed_q)).scalar() or 0

    # Critical + open
    critical_open_q = select(func.count(AnomalyDetection.id)).where(
        and_(AnomalyDetection.severity == "critical", AnomalyDetection.status == "open")
    )
    critical_open = (await session.execute(critical_open_q)).scalar() or 0

    # High + open
    high_open_q = select(func.count(AnomalyDetection.id)).where(
        and_(AnomalyDetection.severity == "high", AnomalyDetection.status == "open")
    )
    high_open = (await session.execute(high_open_q)).scalar() or 0

    return {
        "total": total,
        "open": open_count,
        "investigating": investigating_count,
        "resolved": resolved_count,
        "dismissed": dismissed_count,
        "critical_open": critical_open,
        "high_open": high_open,
    }


@router.get("")
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
            AnomalyDetection.resolved_at,
            AnomalyDetection.resolution_notes,
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
            title = f"{row.anomaly_type.replace(_,  ).title()} — {row.entity_value or unknown}"

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
            "updated_at": row.resolved_at or row.time,
            "resolved_at": row.resolved_at,
            "resolution_notes": row.resolution_notes,
            "events": [],
        })

    return {
        "data": alerts,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": max(1, (total + limit - 1) // limit),
    }


@router.patch("/{alert_id}")
async def update_alert(
    alert_id: str,
    body: dict,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Update an alert status, assignee, and/or resolution notes.

    Status transitions: open → investigating → resolved/dismissed
    Terminal states (resolved/dismissed) cannot be changed.
    """
    # Parse alert ID — strip "ALT-" prefix if present
    try:
        raw_id = alert_id.replace("ALT-", "")
        pk = int(raw_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail=f"Invalid alert ID: {alert_id}")

    # Fetch existing record
    stmt = select(AnomalyDetection).where(AnomalyDetection.id == pk)
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    # ── Status transition validation ──
    new_status = body.get("status")
    if new_status is not None:
        if new_status not in VALID_TRANSITIONS:
            valid = set()
            for v in VALID_TRANSITIONS.values():
                valid.update(v)
            valid.update(VALID_TRANSITIONS.keys())
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status {new_status}. Valid statuses: {sorted(valid)}",
            )

        current_status = record.status
        if current_status in TERMINAL_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot change status from terminal state {current_status}",
            )

        if new_status not in VALID_TRANSITIONS.get(current_status, set()):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid transition from {current_status} to {new_status}. "
                       f"Allowed: {sorted(VALID_TRANSITIONS[current_status])}",
            )

        record.status = new_status

        # Set resolved_at when transitioning to a terminal state
        if new_status in TERMINAL_STATUSES:
            record.resolved_at = datetime.now(timezone.utc)

    # ── Assignee update ──
    if "assignee" in body:
        record.assigned_to = body["assignee"]

    # ── Resolution notes (only meaningful for terminal states) ──
    if "resolution_notes" in body:
        if record.status in TERMINAL_STATUSES:
            record.resolution_notes = body["resolution_notes"]
        else:
            raise HTTPException(
                status_code=422,
                detail="resolution_notes can only be set when status is resolved or dismissed",
            )

    await session.flush()
    await session.refresh(record)

    # Re-fetch with entity name for the response
    detail_stmt = (
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
            AnomalyDetection.resolved_at,
            AnomalyDetection.resolution_notes,
            Entity.entity_value,
        )
        .outerjoin(Entity, AnomalyDetection.entity_id == Entity.id)
        .where(AnomalyDetection.id == pk)
    )
    detail_result = await session.execute(detail_stmt)
    row = detail_result.one()

    risk_score = _severity_to_risk(row.severity, row.score)

    if row.description:
        title = row.description
        if len(title) > 100:
            title = title[:100] + "..."
    else:
        title = f"{row.anomaly_type.replace(_,  ).title()} — {row.entity_value or unknown}"

    return {
        "id": f"ALT-{row.id}",
        "title": title,
        "description": row.description or "",
        "severity": row.severity,
        "status": row.status,
        "assignee": row.assigned_to,
        "entity": row.entity_value or "unknown",
        "risk_score": risk_score,
        "created_at": row.time,
        "updated_at": row.resolved_at or row.time,
        "resolved_at": row.resolved_at,
        "resolution_notes": row.resolution_notes,
        "events": [],
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
