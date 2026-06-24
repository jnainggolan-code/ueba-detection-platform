"""Event repository — data access layer for log events and queries."""

from typing import Optional

from sqlalchemy import func, text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import LogsRaw


class EventRepository:
    """Repository for log_raw table operations."""

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
        """Return total number of events in logs_raw."""
        result = await self.session.execute(
            select(func.count(LogsRaw.id))
        )
        return result.scalar() or 0

    async def count_by_source(self) -> list[dict]:
        """Return event count grouped by source."""
        result = await self.session.execute(
            select(
                LogsRaw.source,
                func.count(LogsRaw.id).label("count"),
            ).group_by(LogsRaw.source)
        )
        return [
            {"source": row.source, "count": row.count}
            for row in result.all()
        ]

    async def count_by_entity(self) -> list[dict]:
        """Return event count grouped by parsed entity value."""
        result = await self.session.execute(
            select(
                LogsRaw.parsed_data["entity_value"].as_string().label("entity"),
                func.count(LogsRaw.id).label("count"),
            )
            .where(LogsRaw.parsed_data.isnot(None))
            .group_by(text("entity"))
            .limit(50)
        )
        return [
            {"entity": row.entity, "count": row.count}
            for row in result.all()
        ]

    async def find_all(
        self,
        offset: int = 0,
        limit: int = 25,
        source: str | None = None,
        entity: str | None = None,
        event_type: str | None = None,
        search: str | None = None,
    ) -> tuple[list[LogsRaw], int]:
        """Return paginated list of events + total count with optional filters."""
        query = select(LogsRaw).order_by(LogsRaw.time.desc())

        if source:
            query = query.where(LogsRaw.source == source)
        if entity:
            query = query.where(LogsRaw.raw_payload["entity_id"].as_string() == entity)
        if event_type:
            query = query.where(LogsRaw.raw_payload["event_type"].as_string() == event_type)
        if search:
            from sqlalchemy import cast, String, and_
            from functools import reduce
            # Multiple keyword search — split by spaces, AND logic
            keywords = [kw.strip() for kw in search.split() if kw.strip()]
            conditions = []
            for kw in keywords:
                pattern = f"%{kw}%"
                kw_cond = cast(LogsRaw.raw_payload, String).ilike(pattern)
                conditions.append(kw_cond)
            if conditions:
                query = query.where(reduce(and_, conditions))

        # Count total first
        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_q)).scalar() or 0

        # Paginate
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        items = list(result.scalars().all())
        return items, total

    async def find_by_id(self, event_id: int) -> LogsRaw | None:
        """Find a single event by its id."""
        result = await self.session.execute(
            select(LogsRaw).where(LogsRaw.id == event_id)
        )
        return result.scalar_one_or_none()
