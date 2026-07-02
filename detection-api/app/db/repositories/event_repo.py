"""Event repository — data access layer for log events and queries."""

import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import func, text, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import LogsRaw

logger = logging.getLogger(__name__)


class EventRepository:
    """Repository for logs_raw table operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert_one(self, event: LogsRaw) -> LogsRaw:
        """Insert a single raw log event."""
        self.session.add(event)
        await self.session.flush()
        return event

    async def insert_batch(self, events: list[LogsRaw]) -> int:
        """Bulk insert multiple events. Returns count inserted."""
        if not events:
            return 0
        self.session.add_all(events)
        await self.session.flush()
        return len(events)

    async def count_total(self) -> int:
        """Return approximate total event count."""
        try:
            result = await self.session.execute(select(func.count(LogsRaw.id)))
            return result.scalar() or 0
        except Exception as exc:
            logger.warning("Count query failed: %s", exc)
            return 0

    async def count_by_source(self) -> list[dict]:
        """Return event count grouped by source (last 7 days only for speed)."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        result = await self.session.execute(
            select(
                LogsRaw.source,
                func.count(LogsRaw.id).label("count"),
            )
            .where(LogsRaw.time >= cutoff)
            .group_by(LogsRaw.source)
        )
        return [
            {"source": row.source, "count": row.count}
            for row in result.all()
        ]

    async def count_by_entity(self) -> list[dict]:
        """Return event count grouped by parsed entity value (last 7 days)."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        try:
            result = await self.session.execute(
                select(
                    LogsRaw.parsed_data["entity_id"].as_string().label("entity"),
                    func.count(LogsRaw.id).label("count"),
                )
                .where(LogsRaw.parsed_data.isnot(None))
                .where(LogsRaw.time >= cutoff)
                .group_by(text("entity"))
                .limit(50)
            )
            return [
                {"entity": row.entity, "count": row.count}
                for row in result.all()
            ]
        except Exception as exc:
            logger.warning("count_by_entity failed: %s", exc)
            return []

    async def find_all(
        self,
        offset: int = 0,
        limit: int = 25,
        source: str | None = None,
        entity: str | None = None,
        event_type: str | None = None,
        search: str | None = None,
        days: int | None = None,
        cursor: str | None = None,
    ) -> tuple[list[LogsRaw], int, str | None]:
        """Return paginated list of events with optional filters.

        Uses keyset (cursor) pagination for O(1) performance regardless
        of page depth. Falls back to offset pagination when no cursor provided.

        Returns: (items, total_count, next_cursor)
        - total_count uses PostgreSQL approximate count (fast, no I/O)
        - next_cursor is None when no more pages exist
        """
        if days is None or days <= 0:
            days = 7
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Build base query
        query = select(LogsRaw).where(LogsRaw.time >= cutoff)

        if source:
            query = query.where(LogsRaw.source == source)
        if entity:
            query = query.where(LogsRaw.parsed_data["entity_id"].as_string() == entity)
        if event_type:
            query = query.where(LogsRaw.parsed_data["event_type"].as_string() == event_type)

        if search:
            keywords = [kw.strip() for kw in search.split() if kw.strip()]
            if keywords:
                tsquery_parts = " | ".join(kw.replace("'", "''") for kw in keywords)
                fts_condition = text(
                    "to_tsvector('simple', coalesce(cast(raw_payload as text), '')) @@ to_tsquery('simple', :tsq)"
                )
                query = query.where(fts_condition).params(tsq=tsquery_parts)

        # --- Keyset pagination ---
        if cursor and not search:
            try:
                cursor_data = json.loads(cursor)
                cursor_time = datetime.fromisoformat(cursor_data["time"])
                cursor_id = cursor_data["id"]
                query = query.where(
                    tuple_(LogsRaw.time, LogsRaw.id) < (cursor_time, cursor_id)
                )
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                logger.warning("Invalid cursor '%s': %s", cursor, exc)
                if offset > 0:
                    query = query.offset(offset)

        if search:
            # For FTS search, skip ORDER BY to let PostgreSQL use the GIN index directly.
            # Results are returned in arbitrary order (fastest path).
            pass
        else:
            query = query.order_by(LogsRaw.time.desc(), LogsRaw.id.desc())

        # --- Approximate count ---
        total = 0
        if not cursor:
            try:
                if search:
                    # FTS count is expensive; use pg_class approximate count instead
                    result = await self.session.execute(
                        text("SELECT COALESCE(SUM(reltuples), 0)::bigint FROM pg_class"
                             " WHERE relname LIKE '_hyper_1_%_chunk'"
                             " AND reltuples > 0")
                    )
                    total = result.scalar() or 0
                else:
                    # Fast index-only count for indexed fields
                    count_query = select(func.count(LogsRaw.id)).where(LogsRaw.time >= cutoff)
                    if source:
                        count_query = count_query.where(LogsRaw.source == source)
                    if entity:
                        count_query = count_query.where(LogsRaw.parsed_data["entity_id"].as_string() == entity)
                    if event_type:
                        count_query = count_query.where(LogsRaw.parsed_data["event_type"].as_string() == event_type)
                    result = await self.session.execute(count_query)
                    total = result.scalar() or 0
            except Exception as exc:
                logger.warning("Count failed: %s", exc)
                total = 0

        # --- Fetch with +1 extra to detect has_more ---
        query = query.limit(limit + 1)
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        has_more = len(items) > limit
        if has_more:
            items = items[:limit]

        # Build next cursor from last item (only for ordered queries)
        next_cursor = None
        if has_more and items and not search:
            last = items[-1]
            next_cursor = json.dumps({
                "time": last.time.isoformat(),
                "id": last.id,
            })

        return items, total, next_cursor

    async def find_by_id(self, event_id: int) -> LogsRaw | None:
        """Find a single event by its id."""
        result = await self.session.execute(
            select(LogsRaw).where(LogsRaw.id == event_id)
        )
        return result.scalar_one_or_none()
