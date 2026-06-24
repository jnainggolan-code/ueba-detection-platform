"""Event service — business logic for event ingestion."""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.event_repo import EventRepository
from app.models.event import LogsRaw
from app.schemas.event import (
    EventCreate,
    BatchEventCreate,
)

logger = logging.getLogger(__name__)


class EventService:
    """Service layer for event ingestion operations."""

    def __init__(self, session: AsyncSession):
        self.repo = EventRepository(session)

    async def ingest_single(
        self, payload: EventCreate, source: str = "api"
    ) -> dict:
        """Validate and insert a single event into logs_raw."""
        now = datetime.now(timezone.utc)
        event = LogsRaw(
            time=payload.timestamp or now,
            source=source,
            source_ip=payload.source_ip,
            log_level=payload.log_level,
            raw_payload=payload.model_dump(mode="json"),
            parsed_data=None,
            parser_version="1.0",
            ingested_at=now,
        )
        created = await self.repo.insert_one(event)
        logger.info(
            "Ingested single event id=%s source=%s", created.id, source
        )
        return {"id": created.id, "status": "stored", "source": source}

    async def ingest_batch(
        self, payload: BatchEventCreate, source: str = "api"
    ) -> dict:
        """Validate and bulk insert up to 1000 events."""
        now = datetime.now(timezone.utc)
        events = []
        for evt in payload.events:
            events.append(
                LogsRaw(
                    time=evt.timestamp or now,
                    source=source,
                    source_ip=evt.source_ip,
                    log_level=evt.log_level,
                    raw_payload=evt.model_dump(mode="json"),
                    parsed_data=None,
                    parser_version="1.0",
                    ingested_at=now,
                )
            )
        count = await self.repo.insert_batch(events)
        logger.info("Ingested batch of %d events source=%s", count, source)
        return {"count": count, "status": "stored", "source": source}

    async def ingest_raw(
        self, payload: dict, source: str = "raw"
    ) -> dict:
        """Ingest raw/arbitrary payload (source-agnostic)."""
        now = datetime.now(timezone.utc)
        event = LogsRaw(
            time=now,
            source=source,
            source_ip=payload.get("source_ip"),
            log_level=payload.get("log_level"),
            raw_payload=payload,
            parsed_data=None,
            parser_version="1.0",
            ingested_at=now,
        )
        created = await self.repo.insert_one(event)
        return {"id": created.id, "status": "stored", "source": source}

    async def ingest_processed(
        self, payload: dict, source: str = "process"
    ) -> dict:
        """Ingest enriched/annotated data with parsed_data populated."""
        now = datetime.now(timezone.utc)
        event = LogsRaw(
            time=payload.get("timestamp", now),
            source=source,
            source_ip=payload.get("source_ip"),
            log_level=payload.get("log_level"),
            raw_payload=payload,
            parsed_data=payload.get("parsed_data") or payload,
            parser_version="2.0",
            ingested_at=now,
        )
        created = await self.repo.insert_one(event)
        return {"id": created.id, "status": "stored", "source": source}

    async def ingest_wazuh(
        self, payload: dict, source: str = "wazuh"
    ) -> dict:
        """Ingest Wazuh-native alert format."""
        now = datetime.now(timezone.utc)
        raw_data = payload.get("data", {})
        event = LogsRaw(
            time=payload.get("timestamp", now),
            source=source,
            source_ip=raw_data.get("srcip"),
            log_level=self._wazuh_level_to_log(payload.get("severity", 0)),
            raw_payload=payload,
            parsed_data={
                "wazuh_rule_id": payload.get("rule_id"),
                "wazuh_rule_description": payload.get("rule_description"),
                "wazuh_severity": payload.get("severity"),
                "mitre_technique_id": payload.get("mitre", {}).get("technique_id"),
                "mitre_technique_name": payload.get("mitre", {}).get("technique_name"),
            },
            parser_version="2.0",
            ingested_at=now,
        )
        created = await self.repo.insert_one(event)
        return {"id": created.id, "status": "stored", "source": source}

    async def get_stats(self) -> dict:
        """Return aggregate statistics about stored events."""
        total = await self.repo.count_total()
        by_source = await self.repo.count_by_source()
        by_entity = await self.repo.count_by_entity()
        return {
            "total_events": total,
            "by_source": by_source,
            "by_entity": by_entity,
        }

    @staticmethod
    def _wazuh_level_to_log(level: int) -> str:
        if level <= 3:
            return "info"
        elif level <= 7:
            return "warning"
        elif level <= 11:
            return "error"
        return "critical"
