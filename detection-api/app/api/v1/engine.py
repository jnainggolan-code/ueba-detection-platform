"""API v1 UEBA engine endpoints — risk, anomaly detection, peer group."""

import time
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text

from app.db.session import get_db_session
from app.services.risk_scoring import RiskScoringService
from app.services.anomaly_detector import AnomalyDetector
from app.models.event import Base, LogsRaw, Entity

# Router definition
router = APIRouter(prefix='/api/ueba', tags=['UEBA Engine'])

# Track application startup time for uptime calculation
start_time = time.time()


# --- Utility Functions ---

def parse_json_field(val: Any) -> Any:
    """Safely parse JSON field from database queries."""
    if not val:
        return {}
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val


# --- Pydantic Schemas for Response Models ---

class HealthResponse(BaseModel):
    status: str
    uptime: float
    version: str


class EntityRiskResponse(BaseModel):
    id: int
    entity_value: str
    risk_score: float
    risk_level: str
    risk_factors: Dict[str, Any]
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    profile_metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None

    class Config:
        from_attributes = True


class RiskHistoryEntry(BaseModel):
    time: Optional[datetime] = None
    overall_score: float
    component_scores: Optional[Dict[str, Any]] = None
    scoring_version: Optional[str] = None


class UserRiskResponse(BaseModel):
    entity: EntityRiskResponse
    history: List[RiskHistoryEntry]


class AnomalyDetectionResponse(BaseModel):
    id: int
    time: Optional[datetime] = None
    entity_id: int
    anomaly_type: str
    severity: str
    score: float
    z_score: float
    description: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    mitre_technique: Optional[str] = None
    mitre_tactic: Optional[str] = None
    status: str


class DetectionsPaginatedResponse(BaseModel):
    detections: List[AnomalyDetectionResponse]
    page: int
    limit: int
    total: int


class PeerComparisonResponse(BaseModel):
    username: str
    user_risk_score: float
    user_risk_level: str
    peer_group_size: int
    peer_avg_risk_score: float
    peer_max_risk_score: float
    peer_min_risk_score: float
    peer_avg_historical_score: float
    comparison_message: str
    peers: List[EntityRiskResponse]


# --- Endpoints ---

@router.get('/health', response_model=HealthResponse)
async def get_health():
    """GET /api/ueba/health — Health check."""
    uptime = time.time() - start_time
    return HealthResponse(
        status="healthy",
        uptime=round(uptime, 2),
        version="1.0.0"
    )


@router.get('/risk/current', response_model=List[EntityRiskResponse])
async def get_current_risks(
    session: AsyncSession = Depends(get_db_session)
) -> List[EntityRiskResponse]:
    """GET /api/ueba/risk/current — All entity risk levels."""
    try:
        stmt = select(Entity).order_by(Entity.risk_score.desc()).limit(100)
        res = await session.execute(stmt)
        entities = res.scalars().all()

        return [
            EntityRiskResponse(
                id=e.id,
                entity_value=e.entity_value,
                risk_score=e.risk_score,
                risk_level=e.risk_level,
                risk_factors=e.risk_factors or {},
                first_seen=e.first_seen,
                last_seen=e.last_seen,
                profile_metadata=e.profile_metadata or {},
                tags=e.tags or []
            )
            for e in entities
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database query error: {str(exc)}")


@router.get('/risk/user/{username}', response_model=UserRiskResponse)
async def get_user_risk(
    username: str,
    session: AsyncSession = Depends(get_db_session)
) -> UserRiskResponse:
    """GET /api/ueba/risk/user/{username} — Single user risk."""
    try:
        stmt = select(Entity).where(Entity.entity_value == username)
        res = await session.execute(stmt)
        entity = res.scalar_one_or_none()

        if not entity:
            raise HTTPException(status_code=404, detail=f"User entity '{username}' not found")

        # Calculate/update risk score with decay
        scoring_service = RiskScoringService(session)
        await scoring_service.calculate_entity_risk(entity.id)
        await session.refresh(entity)

        # Fetch risk score history
        history_query = text("""
            SELECT time, overall_score, component_scores, scoring_version
            FROM risk_scores
            WHERE entity_id = :entity_id
            ORDER BY time DESC
            LIMIT 10
        """)
        history_res = await session.execute(history_query, {"entity_id": entity.id})
        history_rows = history_res.fetchall()

        history = []
        for row in history_rows:
            t = row[0]
            if t and t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            history.append(
                RiskHistoryEntry(
                    time=t,
                    overall_score=row[1],
                    component_scores=parse_json_field(row[2]),
                    scoring_version=row[3]
                )
            )

        return UserRiskResponse(
            entity=EntityRiskResponse(
                id=entity.id,
                entity_value=entity.entity_value,
                risk_score=entity.risk_score,
                risk_level=entity.risk_level,
                risk_factors=entity.risk_factors or {},
                first_seen=entity.first_seen,
                last_seen=entity.last_seen,
                profile_metadata=entity.profile_metadata or {},
                tags=entity.tags or []
            ),
            history=history
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {str(exc)}")


@router.get('/detections', response_model=DetectionsPaginatedResponse)
async def get_detections(
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=50, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_db_session)
) -> DetectionsPaginatedResponse:
    """GET /api/ueba/detections — List anomaly detections."""
    try:
        offset = (page - 1) * limit

        count_query = text("SELECT COUNT(*) FROM anomaly_detections")
        count_res = await session.execute(count_query)
        total = count_res.scalar() or 0

        detections_query = text("""
            SELECT id, time, entity_id, anomaly_type, severity, score,
                   z_score, description, evidence, mitre_technique,
                   mitre_tactic, status
            FROM anomaly_detections
            ORDER BY time DESC
            LIMIT :limit OFFSET :offset
        """)
        detections_res = await session.execute(detections_query, {"limit": limit, "offset": offset})
        rows = detections_res.fetchall()

        detections = []
        for row in rows:
            t = row[1]
            if t and t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            evidence_val = parse_json_field(row[8])
            if not isinstance(evidence_val, dict):
                evidence_val = {"evidence": evidence_val} if evidence_val else {}

            detections.append(
                AnomalyDetectionResponse(
                    id=row[0],
                    time=t,
                    entity_id=row[2],
                    anomaly_type=row[3],
                    severity=row[4],
                    score=row[5],
                    z_score=row[6] if row[6] is not None else 0.0,
                    description=row[7],
                    evidence=evidence_val,
                    mitre_technique=row[9],
                    mitre_tactic=row[10],
                    status=row[11]
                )
            )

        return DetectionsPaginatedResponse(
            detections=detections,
            page=page,
            limit=limit,
            total=total
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {str(exc)}")


@router.get('/peer-group/{username}', response_model=PeerComparisonResponse)
async def get_peer_group_comparison(
    username: str,
    session: AsyncSession = Depends(get_db_session)
) -> PeerComparisonResponse:
    """GET /api/ueba/peer-group/{username} — Peer group comparison."""
    try:
        stmt = select(Entity).where(Entity.entity_value == username)
        res = await session.execute(stmt)
        entity = res.scalar_one_or_none()

        if not entity:
            raise HTTPException(status_code=404, detail=f"User entity '{username}' not found")

        # Calculate/update target entity risk score with decay
        scoring_service = RiskScoringService(session)
        await scoring_service.calculate_entity_risk(entity.id)
        await session.refresh(entity)

        # --- Identify Peer Group ---
        peers: List[Entity] = []

        # Criteria 1: Overlapping tags
        if entity.tags:
            stmt_tags = (
                select(Entity)
                .where(Entity.id != entity.id)
                .where(Entity.tags.overlap(entity.tags))
                .order_by(Entity.risk_score.desc())
                .limit(20)
            )
            res_tags = await session.execute(stmt_tags)
            peers = list(res_tags.scalars().all())

        # Criteria 2: Matching profile metadata keys
        if not peers:
            metadata = entity.profile_metadata or {}
            clauses = []
            for key in ["department", "role", "group"]:
                val = metadata.get(key)
                if val:
                    clauses.append(Entity.profile_metadata[key].as_string() == val)
            if clauses:
                stmt_meta = (
                    select(Entity)
                    .where(Entity.id != entity.id)
                    .where(or_(*clauses))
                    .order_by(Entity.risk_score.desc())
                    .limit(20)
                )
                res_meta = await session.execute(stmt_meta)
                peers = list(res_meta.scalars().all())

        # Criteria 3: Same risk level
        if not peers:
            stmt_lvl = (
                select(Entity)
                .where(Entity.id != entity.id)
                .where(Entity.risk_level == entity.risk_level)
                .order_by(Entity.risk_score.desc())
                .limit(20)
            )
            res_lvl = await session.execute(stmt_lvl)
            peers = list(res_lvl.scalars().all())

        # Criteria 4: Global pool fallback
        if not peers:
            stmt_global = (
                select(Entity)
                .where(Entity.id != entity.id)
                .order_by(Entity.risk_score.desc())
                .limit(20)
            )
            res_global = await session.execute(stmt_global)
            peers = list(res_global.scalars().all())

        # --- Calculate Comparison Aggregates ---
        peer_count = len(peers)
        peer_avg_score = 0.0
        peer_max_score = 0.0
        peer_min_score = 0.0
        peer_avg_historical_score = 0.0

        if peers:
            peer_scores = [p.risk_score for p in peers]
            peer_avg_score = sum(peer_scores) / peer_count
            peer_max_score = max(peer_scores)
            peer_min_score = min(peer_scores)

            peer_ids = [p.id for p in peers]
            query_hist = text("""
                SELECT AVG(overall_score)
                FROM risk_scores
                WHERE entity_id = ANY(:peer_ids)
            """)
            hist_res = await session.execute(query_hist, {"peer_ids": peer_ids})
            peer_avg_historical_score = hist_res.scalar() or 0.0

            if peer_avg_score > 0:
                diff_pct = ((entity.risk_score - peer_avg_score) / peer_avg_score) * 100
                if diff_pct > 0:
                    comparison_message = (
                        f"User risk score ({entity.risk_score:.2f}) is {diff_pct:.2f}% higher "
                        f"than the peer group average ({peer_avg_score:.2f})."
                    )
                elif diff_pct < 0:
                    comparison_message = (
                        f"User risk score ({entity.risk_score:.2f}) is {abs(diff_pct):.2f}% lower "
                        f"than the peer group average ({peer_avg_score:.2f})."
                    )
                else:
                    comparison_message = (
                        f"User risk score ({entity.risk_score:.2f}) is equal to "
                        f"the peer group average ({peer_avg_score:.2f})."
                    )
            else:
                comparison_message = (
                    f"User risk score ({entity.risk_score:.2f}) is consistent "
                    f"with the peer group average."
                )
        else:
            comparison_message = "No similar entities found in the peer group to compare against."

        return PeerComparisonResponse(
            username=entity.entity_value,
            user_risk_score=entity.risk_score,
            user_risk_level=entity.risk_level,
            peer_group_size=peer_count,
            peer_avg_risk_score=round(peer_avg_score, 2),
            peer_max_risk_score=round(peer_max_score, 2),
            peer_min_risk_score=round(peer_min_score, 2),
            peer_avg_historical_score=round(peer_avg_historical_score, 2),
            comparison_message=comparison_message,
            peers=[
                EntityRiskResponse(
                    id=p.id,
                    entity_value=p.entity_value,
                    risk_score=p.risk_score,
                    risk_level=p.risk_level,
                    risk_factors=p.risk_factors or {},
                    first_seen=p.first_seen,
                    last_seen=p.last_seen,
                    profile_metadata=p.profile_metadata or {},
                    tags=p.tags or []
                )
                for p in peers
            ]
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {str(exc)}")
