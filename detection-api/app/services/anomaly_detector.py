from datetime import datetime, timezone
import json
import math
from typing import List, Dict, Any, Optional

from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.event import LogsRaw, Entity, ScoringConfig, BehaviorBaseline, AnomalyDetection

class AnomalyDetector:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def compute_zscore(self, entity_id: int, metric_name: str, value: float) -> dict:
        """
        Query last N baselines for that entity+metric, compute rolling mean/stddev,
        then z-score for the new value. Returns {z_score, mean, stddev, is_anomaly, threshold}.
        """
        # Query last 30 baselines (N=30)
        stmt = select(BehaviorBaseline).where(
            BehaviorBaseline.entity_id == entity_id,
            BehaviorBaseline.metric_name == metric_name
        ).order_by(BehaviorBaseline.time.desc()).limit(30)
        
        res = await self.session.execute(stmt)
        baselines = res.scalars().all()

        if baselines:
            values = [b.metric_value for b in baselines]
            mean = sum(values) / len(values)
            variance = sum((x - mean) ** 2 for x in values) / len(values)
            stddev = math.sqrt(variance)
        else:
            mean = 0.0
            stddev = 1.0

        # Query scoring config for threshold
        stmt_config = select(ScoringConfig).where(ScoringConfig.anomaly_type == metric_name)
        res_config = await self.session.execute(stmt_config)
        config = res_config.scalar_one_or_none()
        threshold = config.z_score_threshold if config else 3.0

        # Calculate Z-score
        if baselines and stddev > 0.0:
            z_score = (value - mean) / stddev
        else:
            z_score = 0.0

        is_anomaly = z_score >= threshold

        return {
            "z_score": z_score,
            "mean": mean,
            "stddev": stddev,
            "is_anomaly": is_anomaly,
            "threshold": threshold
        }

    async def detect_anomalies(self, event: LogsRaw) -> list[dict]:
        """
        Extract entity_id and anomaly_type from event.parsed_data or event.raw_payload.
        Compute z-score for the event. If anomalous, create row in anomaly_detections table.
        Also create row in behavior_baselines for tracking. Use text() for JSONB operators.
        """
        parsed_data = event.parsed_data or {}
        raw_payload = event.raw_payload or {}

        # The entity_value is stored in event.parsed_data['entity_id'] or fallback to raw_payload['entity_id']
        entity_value_str = None
        if isinstance(parsed_data, dict):
            entity_value_str = parsed_data.get('entity_id')
        if entity_value_str is None and isinstance(raw_payload, dict):
            entity_value_str = raw_payload.get('entity_id')

        if not entity_value_str:
            entity_value_str = event.source_ip or event.source or "unknown_entity"

        # Resolve entity ID (integer ID of Entity record)
        stmt_ent = select(Entity).where(Entity.entity_value == str(entity_value_str))
        res_ent = await self.session.execute(stmt_ent)
        entity = res_ent.scalar_one_or_none()
        if not entity:
            entity = Entity(
                entity_value=str(entity_value_str),
                risk_score=0.0,
                risk_level="low",
                risk_factors={}
            )
            self.session.add(entity)
            await self.session.flush()
        entity_id = entity.id

        # Extract anomaly type
        anomaly_type = None
        if isinstance(parsed_data, dict):
            anomaly_type = parsed_data.get('anomaly_type') or parsed_data.get('event_type')
        if not anomaly_type and isinstance(raw_payload, dict):
            anomaly_type = raw_payload.get('anomaly_type') or raw_payload.get('event_type')
        if not anomaly_type:
            anomaly_type = 'unknown_anomaly'

        # Extract metric name and value
        metric_name = None
        if isinstance(parsed_data, dict):
            metric_name = parsed_data.get('metric_name')
        if not metric_name and isinstance(raw_payload, dict):
            metric_name = raw_payload.get('metric_name')
        if not metric_name:
            metric_name = anomaly_type

        value = None
        if isinstance(parsed_data, dict):
            value = parsed_data.get('metric_value') or parsed_data.get('value')
        if value is None and isinstance(raw_payload, dict):
            value = raw_payload.get('metric_value') or raw_payload.get('value')

        try:
            value = float(value) if value is not None else 0.0
        except (ValueError, TypeError):
            value = 0.0

        # Compute z-score
        z_score_res = await self.compute_zscore(entity_id, metric_name, value)
        z_score = z_score_res["z_score"]
        mean = z_score_res["mean"]
        stddev = z_score_res["stddev"]
        is_anomaly = z_score_res["is_anomaly"]
        threshold = z_score_res["threshold"]

        current_time = datetime.now(timezone.utc)

        # Get window start (oldest of last 30 baseline times, or current_time)
        stmt_window = select(BehaviorBaseline.time).where(
            BehaviorBaseline.entity_id == entity_id,
            BehaviorBaseline.metric_name == metric_name
        ).order_by(BehaviorBaseline.time.desc()).limit(30)
        res_window = await self.session.execute(stmt_window)
        baseline_times = res_window.scalars().all()
        
        window_start = baseline_times[-1] if baseline_times else current_time
        if window_start.tzinfo is None:
            window_start = window_start.replace(tzinfo=timezone.utc)
        window_end = current_time

        # Always insert a baseline entry for tracking
        insert_baseline = text("""
            INSERT INTO behavior_baselines (
                entity_id, time, metric_name, metric_value, 
                baseline_mean, baseline_stddev, z_score, is_anomaly, 
                anomaly_threshold, window_start, window_end
            ) VALUES (
                :entity_id, :time, :metric_name, :metric_value, 
                :baseline_mean, :baseline_stddev, :z_score, :is_anomaly, 
                :anomaly_threshold, :window_start, :window_end
            )
        """)
        await self.session.execute(insert_baseline, {
            "entity_id": entity_id,
            "time": current_time,
            "metric_name": metric_name,
            "metric_value": value,
            "baseline_mean": mean,
            "baseline_stddev": stddev,
            "z_score": z_score,
            "is_anomaly": is_anomaly,
            "anomaly_threshold": threshold,
            "window_start": window_start,
            "window_end": window_end
        })

        anomalies = []
        if is_anomaly:
            # Get severity
            severity = None
            if isinstance(parsed_data, dict):
                severity = parsed_data.get('severity') or parsed_data.get('log_level')
            if not severity and isinstance(raw_payload, dict):
                severity = raw_payload.get('severity') or raw_payload.get('log_level')
            if not severity:
                severity = event.log_level or 'medium'

            sev_key = str(severity).lower()

            # Query severity multiplier using text() for JSONB operator ->>
            stmt_weight = select(text("severity_mapping ->> :sev_key")).select_from(ScoringConfig).where(
                ScoringConfig.anomaly_type == anomaly_type
            ).params(sev_key=sev_key)
            
            res_weight = await self.session.execute(stmt_weight)
            severity_mult_str = res_weight.scalar()
            
            try:
                severity_multiplier = float(severity_mult_str) if severity_mult_str is not None else 1.0
            except (ValueError, TypeError):
                severity_multiplier = 1.0

            # Query base weight
            stmt_config = select(ScoringConfig).where(ScoringConfig.anomaly_type == anomaly_type)
            res_config = await self.session.execute(stmt_config)
            config = res_config.scalar_one_or_none()
            base_weight = config.base_weight if config else 10.0
            score = base_weight * severity_multiplier

            # Resolve description & evidence
            description = f"Anomaly of type '{anomaly_type}' detected for entity {entity_value_str} (metric: {metric_name}, value: {value}, z-score: {z_score:.2f}, threshold: {threshold})"
            evidence = {
                "value": value,
                "mean": mean,
                "stddev": stddev,
                "z_score": z_score,
                "threshold": threshold,
                "event_id": event.id,
                "parsed_data": parsed_data,
                "raw_payload": raw_payload
            }

            # Extract MITRE details
            mitre_technique = parsed_data.get('mitre_technique') if isinstance(parsed_data, dict) else None
            if not mitre_technique and isinstance(raw_payload, dict):
                mitre_technique = raw_payload.get('mitre_technique')

            mitre_tactic = parsed_data.get('mitre_tactic') if isinstance(parsed_data, dict) else None
            if not mitre_tactic and isinstance(raw_payload, dict):
                mitre_tactic = raw_payload.get('mitre_tactic')

            # Insert anomaly detection using raw SQL due to incomplete ORM mapping
            insert_anomaly = text("""
                INSERT INTO anomaly_detections (
                    time, entity_id, anomaly_type, severity, score, 
                    z_score, description, evidence, mitre_technique, 
                    mitre_tactic, status
                ) VALUES (
                    :time, :entity_id, :anomaly_type, :severity, :score, 
                    :z_score, :description, :evidence, :mitre_technique, 
                    :mitre_tactic, :status
                ) RETURNING id
            """)
            
            res_anom = await self.session.execute(insert_anomaly, {
                "time": current_time,
                "entity_id": entity_id,
                "anomaly_type": anomaly_type,
                "severity": severity,
                "score": score,
                "z_score": z_score,
                "description": description,
                "evidence": json.dumps(evidence),
                "mitre_technique": mitre_technique,
                "mitre_tactic": mitre_tactic,
                "status": "open"
            })
            anomaly_id = res_anom.scalar()

            # ── Auto-create alert if severity is high or critical ──
            if severity.lower() in ("high", "critical"):
                # Call the DB function fn_generate_alert to create an alert record
                await self.session.execute(
                    text("SELECT fn_generate_alert(:anomaly_id)"),
                    {"anomaly_id": anomaly_id},
                )


            anomalies.append({
                "id": anomaly_id,
                "time": current_time.isoformat(),
                "entity_id": entity_id,
                "anomaly_type": anomaly_type,
                "severity": severity,
                "score": score,
                "z_score": z_score,
                "description": description,
                "evidence": evidence,
                "mitre_technique": mitre_technique,
                "mitre_tactic": mitre_tactic,
                "status": "open"
            })

        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        return anomalies

    async def update_baseline(self, entity_id: int, metric_name: str, value: float) -> None:
        """
        Directly update baseline stats with new value.
        """
        z_score_res = await self.compute_zscore(entity_id, metric_name, value)
        
        current_time = datetime.now(timezone.utc)
        
        stmt_window = select(BehaviorBaseline.time).where(
            BehaviorBaseline.entity_id == entity_id,
            BehaviorBaseline.metric_name == metric_name
        ).order_by(BehaviorBaseline.time.desc()).limit(30)
        res_window = await self.session.execute(stmt_window)
        baseline_times = res_window.scalars().all()
        
        window_start = baseline_times[-1] if baseline_times else current_time
        if window_start.tzinfo is None:
            window_start = window_start.replace(tzinfo=timezone.utc)
        window_end = current_time
        
        insert_baseline = text("""
            INSERT INTO behavior_baselines (
                entity_id, time, metric_name, metric_value, 
                baseline_mean, baseline_stddev, z_score, is_anomaly, 
                anomaly_threshold, window_start, window_end
            ) VALUES (
                :entity_id, :time, :metric_name, :metric_value, 
                :baseline_mean, :baseline_stddev, :z_score, :is_anomaly, 
                :anomaly_threshold, :window_start, :window_end
            )
        """)
        
        await self.session.execute(insert_baseline, {
            "entity_id": entity_id,
            "time": current_time,
            "metric_name": metric_name,
            "metric_value": value,
            "baseline_mean": z_score_res["mean"],
            "baseline_stddev": z_score_res["stddev"],
            "z_score": z_score_res["z_score"],
            "is_anomaly": z_score_res["is_anomaly"],
            "anomaly_threshold": z_score_res["threshold"],
            "window_start": window_start,
            "window_end": window_end
        })
        
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
