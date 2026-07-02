"""Event service — business logic for event ingestion with anomaly detection orchestration."""
import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional
import re

import rq
from app.core.redis import get_sync_redis

_WAZUH_TS_RE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')


def _parse_wazuh_ts(ts_str):
    if not ts_str:
        return datetime.now(timezone.utc)
    if not _WAZUH_TS_RE.match(str(ts_str)):
        return datetime.now(timezone.utc)
    try:
        ts = str(ts_str).replace('+00:00', 'Z').replace('Z', '+00:00')
        if '+' in ts and ':' not in ts[-5:]:
            ts = ts[:-4] + ':' + ts[-4:]
        return datetime.fromisoformat(ts).astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.repositories.event_repo import EventRepository
from app.models.event import LogsRaw
from app.schemas.event import (
    EventCreate,
    BatchEventCreate,
)

logger = logging.getLogger(__name__)

# RQ queue name for engine pipeline jobs
ENGINE_PIPELINE_QUEUE = "engine-pipeline"

# --- Redis cache config ---
SEARCH_CACHE_TTL = 60          # seconds: short TTL for freshness
SEARCH_CACHE_PREFIX = "es:search:"   # key prefix for search result cache


def _search_cache_key(
    page: int, limit: int, source: str | None = None,
    entity: str | None = None, event_type: str | None = None,
    search: str | None = None, days: int | None = 7,
    cursor: str | None = None,
) -> str:
    """Generate a deterministic cache key from query parameters."""
    parts = [
        f"l={limit}",
        f"d={days or 7}",
        f"s={source or ''}",
        f"e={entity or ''}",
        f"et={event_type or ''}",
        f"q={search or ''}",
        f"c={cursor or ''}",
        f"p={page}",
    ]
    raw = ":".join(parts)
    # Hash to keep keys short
    key_hash = hashlib.md5(raw.encode()).hexdigest()
    return f"{SEARCH_CACHE_PREFIX}{key_hash}"


def _get_cache_generation() -> int:
    """Get current cache generation number. Returns 0 if not set."""
    try:
        redis = get_sync_redis()
        return int(redis.get("es:search:generation") or 0)
    except Exception:
        return 0


def _enqueue_engine_pipeline(event: LogsRaw) -> bool:
    """Enqueue event ID to RQ 'engine-pipeline' queue.

    Worker fetches the full event from DB by ID.
    Returns True if enqueued successfully, False otherwise.
    """
    try:
        redis_conn = get_sync_redis()
        queue = rq.Queue(ENGINE_PIPELINE_QUEUE, connection=redis_conn)

        queue.enqueue(
            "app.worker.run_engine_pipeline",
            event.id,
            job_timeout=300,
            result_ttl=3600,
            failure_ttl=86400,
        )
        logger.debug(
            "Enqueued engine pipeline job for event id=%s", event.id
        )
        return True
    except Exception as exc:
        logger.error(
            "Failed to enqueue engine pipeline for event id=%s: %s",
            event.id, exc, exc_info=True,
        )
        return False


class EventService:
    """Service layer for event ingestion operations."""

    def __init__(self, session: AsyncSession):
        self.repo = EventRepository(session)
        self._session = session
        pass

    async def _cache_get(self, key: str) -> dict | None:
        """Get cached search result."""
        try:
            redis = get_sync_redis()
            data = redis.get(key)
            if data:
                return json.loads(data)
        except Exception as exc:
            logger.debug("Cache get failed: %s", exc)
        return None

    async def _cache_set(self, key: str, data: dict) -> None:
        """Store search result in cache with TTL."""
        try:
            redis = get_sync_redis()
            redis.setex(key, SEARCH_CACHE_TTL, json.dumps(data))
        except Exception as exc:
            logger.debug("Cache set failed: %s", exc)

    async def ingest_single(
        self, payload: EventCreate, source: str = "api",
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

        # Cache expires naturally via TTL

        # Enqueue background engine pipeline via RQ
        _enqueue_engine_pipeline(created)

        return {"id": created.id, "status": "stored", "source": source}

    async def ingest_batch(
        self, payload: BatchEventCreate, source: str = "api",
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

        # Cache expires naturally via TTL

        # Enqueue background engine pipeline for each event via RQ
        for evt in events:
            _enqueue_engine_pipeline(evt)

        return {"count": count, "status": "stored", "source": source}

    async def ingest_raw(
        self, payload: dict, source: str = "raw",
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

        _enqueue_engine_pipeline(created)

        return {"id": created.id, "status": "stored", "source": source}

    async def ingest_processed(
        self, payload: dict, source: str = "process",
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

        _enqueue_engine_pipeline(created)

        return {"id": created.id, "status": "stored", "source": source}

    async def ingest_wazuh(
        self, payload: dict, source: str = "wazuh",
    ) -> dict:
        """Ingest Wazuh-native alert format (standard alerts.json format)."""
        now = datetime.now(timezone.utc)
        rule = payload.get("rule", {})
        agent_data = payload.get("agent", {})
        raw_data = payload.get("data", {})
        location = payload.get("location", "unknown")

        # Extract MITRE data (Wazuh format: list under rule.mitre.id)
        mitre = rule.get("mitre", {})
        mitre_ids = mitre.get("id", [])
        mitre_technique_id = mitre_ids[0] if mitre_ids else None

        # Determine entity from agent name or manager name
        entity_id = agent_data.get("name") or payload.get("manager", {}).get("name", "unknown")

        # Extract source IP
        source_ip = agent_data.get("ip") or raw_data.get("srcip")

        # Determine event_type from rule groups or decoder
        groups = rule.get("groups", [])
        decoder_name = payload.get("decoder", {}).get("name", "")
        event_type = "wazuh_" + str(rule.get("id", "unknown"))
        if "windows" in groups:
            win_sys = raw_data.get("win", {}).get("system", {})
            eid = win_sys.get("eventID", "unknown")
            event_type = "windows_" + str(eid)
        elif "authentication" in groups or "pam" in groups:
            event_type = "authentication"
        elif "network" in groups or "firewall" in groups:
            event_type = "network_connection"
        elif "syslog" in groups:
            event_type = "syslog"

        # Extract meaningful details from raw data
        details = {}
        if location == "journald":
            for k in ["srcuser", "dstuser", "uid"]:
                if raw_data.get(k):
                    details[k] = raw_data[k]
        elif "win" in raw_data:
            win_sys = raw_data["win"].get("system", {})
            for k in ["eventID", "providerName", "computer"]:
                v = win_sys.get(k)
                if v:
                    details[k] = v
            msg = win_sys.get("message", "") or ""
            if msg:
                details["message"] = msg[:500]
        else:
            # For other data, include first 5 keys from raw_data
            count = 0
            for k, v in raw_data.items():
                if count >= 5:
                    break
                if v and not isinstance(v, (dict, list)):
                    details[k] = v
                    count += 1

        event = LogsRaw(
            time=_parse_wazuh_ts(payload.get("timestamp")),
            source=source,
            source_ip=source_ip,
            log_level=self._wazuh_level_to_log(rule.get("level", 0)),
            raw_payload=payload,
            parsed_data={
                "wazuh_rule_id": rule.get("id"),
                "wazuh_rule_description": rule.get("description"),
                "wazuh_level": rule.get("level"),
                "entity_id": entity_id,
                "event_type": event_type,
                "event_details": details,
                "mitre_technique_id": mitre_technique_id,
                "mitre_technique_name": mitre.get("technique", [None])[0] if mitre.get("technique") else None,
                "location": location,
                "agent_id": agent_data.get("id"),
                "agent_name": agent_data.get("name"),
                "groups": groups,
                "decoder": decoder_name,
            },
            parser_version="2.0",
            ingested_at=now,
        )
        created = await self.repo.insert_one(event)

        _enqueue_engine_pipeline(created)

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

    async def list_events(
        self, page: int = 1, limit: int = 25,
        source: str | None = None,
        entity: str | None = None,
        event_type: str | None = None,
        search: str | None = None,
        days: int | None = None,
        cursor: str | None = None,
    ) -> dict:
        """List events with pagination and optional filters.

        Uses cursor-based (keyset) pagination for O(1) performance.
        Falls back to offset-based pagination for backward compatibility.

        Returns:
            dict with keys: data, total, page, limit, total_pages,
                            cursor (next cursor), has_more
        """
        # --- Redis cache lookup ---
        cache_key = _search_cache_key(
            page=page, limit=limit, source=source,
            entity=entity, event_type=event_type,
            search=search, days=days, cursor=cursor,
        )
        cached = await self._cache_get(cache_key)
        if cached is not None:
            logger.debug("Search cache HIT for key=%s", cache_key)
            return cached

        # --- Database query ---
        offset = (page - 1) * limit if page > 1 and not cursor else 0
        items, total, next_cursor = await self.repo.find_all(
            offset=offset, limit=limit,
            source=source, entity=entity,
            event_type=event_type, search=search,
            days=days, cursor=cursor,
        )

        # Build response: try to provide total from first page
        total_pages = 1
        if total > 0:
            total_pages = max(1, (total + limit - 1) // limit)

        result = {
            "data": [self._event_to_dict(e) for e in items],
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "cursor": next_cursor,
            "has_more": next_cursor is not None,
        }

        # Cache only first page (no cursor) to keep cache simple
        if not cursor:
            await self._cache_set(cache_key, result)

        return result

    async def get_event_by_id(self, event_id: int) -> dict:
        """Get a single event by its id."""
        event = await self.repo.find_by_id(event_id)
        if not event:
            raise ValueError(f"Event {event_id} not found")
        return self._event_to_dict(event)

    @staticmethod
    def _calc_risk(log_level: str) -> int:
        _map = {"info": 10, "warning": 30, "error": 60, "critical": 90}
        return _map.get(log_level, 25)

    @staticmethod
    def _event_to_dict(event) -> dict:
        """Convert a LogsRaw ORM instance to a serializable dict."""
        return {
            "id": event.id,
            "timestamp": event.time.isoformat() if event.time else None,
            "source": event.source,
            "source_ip": event.source_ip,
            "log_level": event.log_level,
            "event_type": event.parsed_data.get("event_type", "unknown") if event.parsed_data else "unknown",
            "entity": event.parsed_data.get("entity_id", "unknown") if event.parsed_data else "unknown",
            "risk_score": EventService._calc_risk(event.log_level),
            "details": event.raw_payload if event.raw_payload else {},
            "raw_data": json.dumps(event.raw_payload) if event.raw_payload else "{}",
            "raw_payload": event.raw_payload,
            "parsed_data": event.parsed_data,
            "ingested_at": event.ingested_at.isoformat() if event.ingested_at else None,
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
