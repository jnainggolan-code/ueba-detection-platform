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
