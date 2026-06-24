"""SQLAlchemy ORM models for the detection database."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, BIGINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class LogsRaw(Base):
    """Raw log events — the unified ingestion table (hypertable)."""

    __tablename__ = "logs_raw"

    id: Mapped[int] = mapped_column(
        BIGINT, primary_key=True, autoincrement=True
    )
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    source_ip = Column(INET, nullable=True)
    log_level: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )
    raw_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False
    )
    parsed_data = Column(JSONB, nullable=True)
    parser_version: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    processed: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<LogsRaw id={self.id} source={self.source} "
            f"time={self.time}>"
        )
