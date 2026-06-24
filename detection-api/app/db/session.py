"""Async database session factory and connection management."""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> dict:
    """Ping the database and return connection status."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                __import__("sqlalchemy").text("SELECT 1 AS alive")
            )
            row = result.one()
            return {"status": "ok", "db_connected": row.alive == 1}
    except Exception as exc:
        return {"status": "error", "db_connected": False, "detail": str(exc)}
