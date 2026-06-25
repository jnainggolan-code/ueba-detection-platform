"""Rule Engine Service — evaluate custom rules against events."""

import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import LogsRaw, AnomalyDetection
from app.models.rule import CustomRule

logger = logging.getLogger(__name__)


class RuleEngineService:
    """Evaluates custom detection rules against ingested events."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_field_value(self, field: str, event: LogsRaw, risk_result: dict | None) -> Any:
        """Resolve field value from event or risk result."""
        # Direct event fields
        direct_fields = {
            "event_type": lambda: (
                event.parsed_data.get("event_type") if isinstance(event.parsed_data, dict) else None
            ),
            "source": lambda: event.source,
            "source_ip": lambda: str(event.source_ip) if event.source_ip else None,
            "log_level": lambda: event.log_level,
            "entity": lambda: (
                event.parsed_data.get("entity_id") or event.parsed_data.get("entity_value")
                if isinstance(event.parsed_data, dict) else None
            ),
        }
        if field in direct_fields:
            return direct_fields[field]()

        # Risk result fields
        risk_fields = {
            "risk_score": lambda: risk_result.get("overall_score") if risk_result else None,
            "risk_level": lambda: risk_result.get("risk_level") if risk_result else None,
            "is_anomaly": lambda: risk_result.get("is_anomaly") if risk_result else None,
        }
        if field in risk_fields:
            return risk_fields[field]()

        # Parsed data nested fields
        if field.startswith("parsed_data."):
            key = field[len("parsed_data."):]
            if isinstance(event.parsed_data, dict):
                return event.parsed_data.get(key)
            return None

        # Raw payload nested fields
        if field.startswith("raw_payload."):
            key = field[len("raw_payload."):]
            if isinstance(event.raw_payload, dict):
                return event.raw_payload.get(key)
            return None

        return None

    @staticmethod
    def _evaluate_single(value: Any, operator: str, expected: Any) -> bool:
        """Evaluate a single condition."""
        try:
            if operator == "equals":
                return str(value) == str(expected)
            elif operator == "not_equals":
                return str(value) != str(expected)
            elif operator == "contains":
                return expected in str(value) if value else False
            elif operator == "greater_than":
                return float(value) > float(expected) if value else False
            elif operator == "less_than":
                return float(value) < float(expected) if value else False
            elif operator == "in_list":
                return str(value) in [str(v) for v in (expected if isinstance(expected, list) else [expected])]
            elif operator == "not_in_list":
                return str(value) not in [str(v) for v in (expected if isinstance(expected, list) else [expected])]
            elif operator == "matches_regex":
                return bool(re.search(str(expected), str(value))) if value else False
            return False
        except (ValueError, TypeError) as exc:
            logger.debug("Condition eval error: %s", exc)
            return False

    async def _evaluate_condition_group(
        self, group: dict, event: LogsRaw, risk_result: dict | None
    ) -> bool:
        """Evaluate a group of conditions with AND/OR logic."""
        logic = group.get("logic", "AND").upper()
        conditions = group.get("conditions", [])

        if not conditions:
            return True

        results = []
        for cond in conditions:
            if "conditions" in cond:
                # Nested group
                result = await self._evaluate_condition_group(cond, event, risk_result)
            elif "field" in cond and "operator" in cond:
                value = await self._get_field_value(cond["field"], event, risk_result)
                result = self._evaluate_single(value, cond["operator"], cond.get("value"))
            else:
                result = True

            results.append(result)

        if logic == "AND":
            return all(results)
        else:  # OR
            return any(results)

    async def _check_frequency(
        self, rule: CustomRule, event: LogsRaw, risk_result: dict | None
    ) -> bool:
        """Check frequency condition: count matching events in N minutes."""
        conditions = rule.conditions or {}
        frequency = conditions.get("frequency")

        if not frequency:
            return True

        minutes = int(frequency.get("minutes", 5))
        min_count = int(frequency.get("min_count", 3))
        filter_field = frequency.get("field")
        filter_value = frequency.get("value")

        if not filter_field or not filter_value:
            return True

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        # Build a query to count matching events in the time window
        query = select(func.count(LogsRaw.id)).where(
            LogsRaw.ingested_at >= cutoff
        )

        # Add the filter condition
        if filter_field == "source_ip":
            query = query.where(LogsRaw.source_ip == filter_value)
        elif filter_field == "source":
            query = query.where(LogsRaw.source == filter_value)
        elif filter_field == "event_type":
            query = query.where(
                LogsRaw.parsed_data["event_type"].as_string() == filter_value
            )
        elif filter_field == "entity":
            query = query.where(
                LogsRaw.parsed_data["entity_value"].as_string() == filter_value
            )

        result = await self.session.execute(query)
        count = result.scalar() or 0

        return count >= min_count

    async def evaluate_rule(
        self, rule: CustomRule, event: LogsRaw, risk_result: dict | None
    ) -> bool:
        """Evaluate a single rule against an event."""
        conditions = rule.conditions or {}

        # Check conditions
        conditions_passed = await self._evaluate_condition_group(conditions, event, risk_result)
        if not conditions_passed:
            return False

        # Check frequency if configured
        frequency_passed = await self._check_frequency(rule, event, risk_result)
        if not frequency_passed:
            return False

        return True

    async def execute_action(self, rule: CustomRule, event: LogsRaw) -> dict | None:
        """Execute rule action — create alert in anomaly_detections."""
        action = rule.action or {}

        if action.get("type") != "create_alert":
            return None

        # Resolve entity_id
        entity_id = None
        if isinstance(event.parsed_data, dict):
            eid = event.parsed_data.get("entity_id")
            if eid is not None:
                try:
                    entity_id = int(eid)
                except (ValueError, TypeError):
                    pass

        # Build title and description from templates
        title = action.get("title", f"Rule triggered: {rule.name}")
        description = action.get("description", f"Custom rule '{rule.name}' matched event {event.id}")
        severity = action.get("severity", "medium")

        # Map severity to risk score for frontend consistency
        severity_scores = {"critical": 80, "high": 60, "medium": 40, "low": 20}
        risk_score = severity_scores.get(severity, 40)

        alert = AnomalyDetection(
            entity_id=entity_id,
            anomaly_type=f"custom_rule_{rule.id}",
            severity=severity,
            score=float(risk_score),
            z_score=None,
            description=description[:500] if description else description,
            evidence={
                "rule_id": rule.id,
                "rule_name": rule.name,
                "event_id": event.id,
                "event_time": event.time.isoformat() if event.time else None,
            },
            mitre_technique=action.get("mitre_technique"),
            mitre_tactic=action.get("mitre_tactic"),
            status="open",
            time=datetime.now(timezone.utc),
        )
        self.session.add(alert)
        await self.session.flush()

        logger.info(
            "Rule '%s' (id=%s) triggered alert %s for event id=%s",
            rule.name, rule.id, alert.id, event.id
        )

        return {
            "alert_id": alert.id,
            "rule_id": rule.id,
            "rule_name": rule.name,
            "severity": severity,
            "title": title,
            "description": description,
        }

    async def evaluate_all_rules(
        self, event: LogsRaw, risk_result: dict | None = None
    ) -> list[dict]:
        """Evaluate all enabled rules against an event. Returns triggered actions."""
        # Load all enabled rules ordered by priority
        stmt = (
            select(CustomRule)
            .where(CustomRule.enabled == True)
            .order_by(CustomRule.priority.desc())
        )
        result = await self.session.execute(stmt)
        rules = result.scalars().all()

        if not rules:
            return []

        triggered = []
        for rule in rules:
            try:
                matched = await self.evaluate_rule(rule, event, risk_result)
                if matched:
                    action_result = await self.execute_action(rule, event)
                    if action_result:
                        triggered.append(action_result)
            except Exception as exc:
                logger.error(
                    "Rule evaluation failed for rule id=%s: %s",
                    rule.id, exc, exc_info=True
                )

        return triggered
