from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.event import Base, LogsRaw, Entity, ScoringConfig, BehaviorBaseline, RiskScore

def get_risk_level(score: float) -> str:
    """
    Determine risk level classification based on overall risk score.
    """
    if score >= 80.0:
        return 'critical'
    elif score >= 60.0:
        return 'high'
    elif score >= 30.0:
        return 'medium'
    return 'low'


import re as _entity_re

_IP_RE = _entity_re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')

def _detect_entity_type(entity_value: str) -> str:
    """Detect entity type from its value."""
    if not entity_value or entity_value in ('unknown', 'unknown_entity'):
        return 'unknown'
    if _IP_RE.match(entity_value):
        return 'ip'
    if '@' in entity_value:
        return 'email'
    if entity_value.islower() and len(entity_value.split()) == 1:
        return 'user'
    return 'unknown'


class RiskScoringService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def calculate_entity_risk(self, entity_id: int) -> dict:
        """
        Calculate and update the current decayed risk score of the entity.
        Returns a dictionary representing the entity's risk metadata.
        """
        stmt = select(Entity).where(Entity.id == entity_id)
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        if not entity:
            return {
                "entity_id": entity_id,
                "risk_score": 0.0,
                "risk_level": "low",
                "risk_factors": {}
            }

        # Retrieve the latest risk score recorded for the entity
        stmt_score = select(RiskScore).where(
            RiskScore.entity_id == entity_id
        ).order_by(RiskScore.time.desc()).limit(1)
        res_score = await self.session.execute(stmt_score)
        latest_score = res_score.scalar_one_or_none()

        if latest_score:
            now = datetime.now(timezone.utc)
            latest_time = latest_score.time
            if latest_time.tzinfo is None:
                latest_time = latest_time.replace(tzinfo=timezone.utc)
            
            elapsed_seconds = (now - latest_time).total_seconds()
            elapsed_days = max(0.0, elapsed_seconds / 86400.0)
            decay_factor = latest_score.decay_factor if latest_score.decay_factor is not None else 0.95

            current_score = latest_score.overall_score * (decay_factor ** elapsed_days)
            entity.risk_score = max(0.0, current_score)
            entity.risk_level = get_risk_level(entity.risk_score)
            
            # Decay individual components in risk factors too
            decayed_factors = {}
            for comp, info in (entity.risk_factors or {}).items():
                if isinstance(info, dict) and "added_risk" in info:
                    new_val = info["added_risk"] * (decay_factor ** elapsed_days)
                    if new_val >= 0.1:
                        decayed_factors[comp] = {
                            **info,
                            "added_risk": new_val
                        }
            entity.risk_factors = decayed_factors
            
            await self.session.commit()

        return {
            "entity_id": entity.id,
            "entity_value": entity.entity_value,
            "risk_score": entity.risk_score,
            "risk_level": entity.risk_level,
            "risk_factors": entity.risk_factors
        }

    async def update_risk_score(self, event: LogsRaw) -> dict:
        """
        Orchestrates risk scoring upon receiving an event:
        - Resolves entity identity and anomaly type.
        - Calculates baseline z-score.
        - Checks config threshold, severity, and cooldown.
        - Calculates new score applying decay to the previous score.
        - Saves new RiskScore and updates the Entity risk status.
        """
        # 1. Resolve anomaly type
        anomaly_type = None
        parsed_data = event.parsed_data or {}
        raw_payload = event.raw_payload or {}
        
        if isinstance(parsed_data, dict):
            anomaly_type = parsed_data.get('event_type') or parsed_data.get('anomaly_type')
        if not anomaly_type and isinstance(raw_payload, dict):
            anomaly_type = raw_payload.get('event_type') or raw_payload.get('anomaly_type')
        if not anomaly_type:
            anomaly_type = 'unknown_anomaly'

        # 2. Resolve entity ID and entity value
        entity_id = None
        entity_value = None
        
        if isinstance(parsed_data, dict):
            entity_id = parsed_data.get('entity_id')
            entity_value = parsed_data.get('entity_value') or parsed_data.get('username') or parsed_data.get('user')
        if entity_id is None and isinstance(raw_payload, dict):
            entity_id = raw_payload.get('entity_id')
            entity_value = entity_value or raw_payload.get('entity_value') or raw_payload.get('username') or raw_payload.get('user')
            
        if not entity_value:
            entity_value = event.source_ip or event.source or "unknown_entity"
            
        if entity_id is not None:
            try:
                entity_id = int(entity_id)
            except (ValueError, TypeError):
                entity_id = None

        if entity_id is None:
            # Query entity by value or create if doesn't exist
            stmt_ent = select(Entity).where(Entity.entity_value == str(entity_value))
            res_ent = await self.session.execute(stmt_ent)
            entity = res_ent.scalar_one_or_none()
            if not entity:
                entity = Entity(
                    entity_type=_detect_entity_type(str(entity_value)),
                    entity_value=str(entity_value),
                    first_seen=datetime.now(timezone.utc),
                    last_seen=datetime.now(timezone.utc),
                    risk_score=0.0,
                    risk_level="low",
                    risk_factors={}
                )
                self.session.add(entity)
                await self.session.flush()
            entity_id = entity.id
        else:
            stmt_ent = select(Entity).where(Entity.id == entity_id)
            res_ent = await self.session.execute(stmt_ent)
            entity = res_ent.scalar_one_or_none()
            if not entity:
                entity = Entity(
                    id=entity_id,
                    entity_type=_detect_entity_type(str(entity_value or f"entity_{entity_id}")),
                    entity_value=str(entity_value or f"entity_{entity_id}"),
                    first_seen=datetime.now(timezone.utc),
                    last_seen=datetime.now(timezone.utc),
                    risk_score=0.0,
                    risk_level="low",
                    risk_factors={}
                )
                self.session.add(entity)
                await self.session.flush()

        # 3. Retrieve scoring config
        stmt_conf = select(ScoringConfig).where(
            ScoringConfig.anomaly_type == anomaly_type,
            ScoringConfig.enabled == True
        )
        res_conf = await self.session.execute(stmt_conf)
        config = res_conf.scalar_one_or_none()

        if not config:
            # Default fallback parameters
            base_weight = 10.0
            z_score_threshold = 3.0
            severity_mapping = {"low": 0.5, "medium": 1.0, "high": 2.0, "critical": 4.0}
            decay_enabled = True
            decay_factor = 0.95
            cooldown_minutes = 60
        else:
            base_weight = config.base_weight
            z_score_threshold = config.z_score_threshold
            severity_mapping = config.severity_mapping or {}
            decay_enabled = config.decay_enabled
            decay_factor = config.decay_factor if config.decay_factor is not None else 0.95
            cooldown_minutes = config.cooldown_minutes or 60

        # 4. Determine metric details and query baseline to compute Z-score
        metric_name = None
        metric_value = None
        if isinstance(parsed_data, dict):
            metric_name = parsed_data.get('metric_name')
            metric_value = parsed_data.get('metric_value') or parsed_data.get('value')
        if not metric_name and isinstance(raw_payload, dict):
            metric_name = raw_payload.get('metric_name')
            metric_value = metric_value or raw_payload.get('metric_value') or raw_payload.get('value')
            
        if not metric_name:
            metric_name = anomaly_type

        stmt_base = select(BehaviorBaseline).where(
            BehaviorBaseline.entity_id == entity_id,
            BehaviorBaseline.metric_name == metric_name
        ).order_by(BehaviorBaseline.time.desc()).limit(1)
        res_base = await self.session.execute(stmt_base)
        baseline = res_base.scalar_one_or_none()

        z_score = 0.0
        baseline_mean = 0.0
        baseline_stddev = 1.0

        if baseline:
            baseline_mean = baseline.baseline_mean or 0.0
            baseline_stddev = baseline.baseline_stddev or 1.0
            if metric_value is not None:
                try:
                    val_f = float(metric_value)
                    if baseline_stddev > 0:
                        z_score = (val_f - baseline_mean) / baseline_stddev
                    else:
                        z_score = 0.0
                except (ValueError, TypeError):
                    z_score = baseline.z_score or 0.0
            else:
                z_score = baseline.z_score or 0.0
        else:
            # Fallback if no baseline is recorded yet, check if event has z_score
            event_z = None
            if isinstance(parsed_data, dict):
                event_z = parsed_data.get('z_score')
            if event_z is None and isinstance(raw_payload, dict):
                event_z = raw_payload.get('z_score')
            if event_z is not None:
                try:
                    z_score = float(event_z)
                except (ValueError, TypeError):
                    z_score = 0.0
            else:
                z_score = 0.0

        is_anomaly = z_score >= z_score_threshold
        event_time = getattr(event, 'time', None)
        if not event_time:
            event_time = datetime.now(timezone.utc)
        elif event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        # Record behavior baseline calculation
        new_baseline = BehaviorBaseline(
            entity_id=entity_id,
            time=event_time,
            metric_name=metric_name,
            metric_value=float(metric_value) if metric_value is not None else 0.0,
            baseline_mean=baseline_mean,
            baseline_stddev=baseline_stddev,
            z_score=z_score,
            is_anomaly=is_anomaly,
            anomaly_threshold=z_score_threshold
        )
        self.session.add(new_baseline)

        # 5. Check Cooldown
        in_cooldown = False
        if cooldown_minutes > 0:
            cooldown_cutoff = event_time - timedelta(minutes=cooldown_minutes)
            stmt_cooldown = select(func.count()).select_from(RiskScore).where(
                RiskScore.entity_id == entity_id,
                RiskScore.time >= cooldown_cutoff,
                text("component_scores ->> :anomaly_type IS NOT NULL")
            ).params(anomaly_type=anomaly_type)
            res_cooldown = await self.session.execute(stmt_cooldown)
            if (res_cooldown.scalar() or 0) > 0:
                in_cooldown = True

        # 6. Fetch previous risk score to apply decay
        stmt_prev = select(RiskScore).where(
            RiskScore.entity_id == entity_id
        ).order_by(RiskScore.time.desc()).limit(1)
        res_prev = await self.session.execute(stmt_prev)
        prev_score = res_prev.scalar_one_or_none()

        prev_overall = 0.0
        prev_time = None
        prev_components = {}

        if prev_score:
            prev_overall = prev_score.overall_score
            prev_time = prev_score.time
            if prev_time and prev_time.tzinfo is None:
                prev_time = prev_time.replace(tzinfo=timezone.utc)
            prev_components = prev_score.component_scores or {}

        current_decay_factor = decay_factor if decay_enabled else 1.0
        decayed_score = prev_overall

        if prev_time and current_decay_factor < 1.0:
            elapsed_seconds = (event_time - prev_time).total_seconds()
            elapsed_days = max(0.0, elapsed_seconds / 86400.0)
            decayed_score = prev_overall * (current_decay_factor ** elapsed_days)

        # 7. Add incremental risk if anomaly is triggered and not in cooldown
        added_risk = 0.0
        if is_anomaly and not in_cooldown:
            severity = None
            if isinstance(parsed_data, dict):
                severity = parsed_data.get('severity') or parsed_data.get('log_level')
            if not severity and isinstance(raw_payload, dict):
                severity = raw_payload.get('severity') or raw_payload.get('log_level')
            if not severity:
                severity = event.log_level or 'medium'
            
            sev_key = str(severity).lower()
            severity_multiplier = severity_mapping.get(sev_key, 1.0)
            added_risk = base_weight * severity_multiplier

        new_overall = max(0.0, decayed_score + added_risk)

        # Decay component scores
        new_components = {}
        if prev_time and current_decay_factor < 1.0:
            elapsed_seconds = (event_time - prev_time).total_seconds()
            elapsed_days = max(0.0, elapsed_seconds / 86400.0)
            for comp, val in prev_components.items():
                decayed_val = float(val) * (current_decay_factor ** elapsed_days)
                if decayed_val >= 0.1:
                    new_components[comp] = decayed_val
        else:
            for comp, val in prev_components.items():
                if float(val) >= 0.1:
                    new_components[comp] = float(val)

        if added_risk > 0:
            new_components[anomaly_type] = new_components.get(anomaly_type, 0.0) + added_risk

        # 8. Record new risk score
        new_risk_score = RiskScore(
            entity_id=entity_id,
            time=event_time,
            overall_score=new_overall,
            component_scores=new_components,
            scoring_version='1.0',
            triggered_by=event.id,
            decay_factor=current_decay_factor
        )
        self.session.add(new_risk_score)

        # 9. Update the Entity's aggregate status
        entity.risk_score = new_overall
        entity.risk_level = get_risk_level(new_overall)
        
        # Sync risk factors details in entity
        risk_factors = dict(entity.risk_factors or {})
        if added_risk > 0:
            risk_factors[anomaly_type] = {
                "last_triggered": event_time.isoformat(),
                "z_score": z_score,
                "added_risk": added_risk
            }
        # Prune decayed factors that are no longer significant
        for comp in list(risk_factors.keys()):
            if comp not in new_components:
                risk_factors.pop(comp, None)
            else:
                risk_factors[comp]["added_risk"] = new_components[comp]
        entity.risk_factors = risk_factors

        await self.session.commit()

        return {
            "entity_id": entity_id,
            "overall_score": new_overall,
            "decayed_score": decayed_score,
            "added_risk": added_risk,
            "is_anomaly": is_anomaly,
            "in_cooldown": in_cooldown,
            "risk_level": entity.risk_level,
            "component_scores": new_components
        }

    async def get_risk_timeline(self, entity_id: int, days: int = 7) -> list:
        """
        Retrieve historical risk scores for a given entity within the specified number of days.
        """
        cutoff_time = func.now() - text(f"INTERVAL '{days} days'")
        stmt = select(RiskScore).where(
            RiskScore.entity_id == entity_id,
            RiskScore.time >= cutoff_time
        ).order_by(RiskScore.time.asc())

        res = await self.session.execute(stmt)
        timeline = res.scalars().all()

        return [
            {
                "id": item.id,
                "entity_id": item.entity_id,
                "time": item.time.isoformat() if item.time else None,
                "overall_score": item.overall_score,
                "component_scores": item.component_scores,
                "scoring_version": item.scoring_version,
                "triggered_by": item.triggered_by,
                "decay_factor": item.decay_factor
            }
            for item in timeline
        ]
