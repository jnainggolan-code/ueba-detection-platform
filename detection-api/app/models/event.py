"""SQLAlchemy ORM models for the detection database."""
from typing import Optional


from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, BIGINT, ARRAY
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


class Entity(Base):
    """Entity table — user/host/device profile with risk data."""

    __tablename__ = "entities"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entity_value: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    first_seen = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    profile_metadata = Column(JSONB, nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    risk_factors = Column(JSONB, nullable=True)
    tags = Column(ARRAY(Text()), nullable=True)


class RiskScore(Base):
    """Risk scores hypertable — time-series of entity risk scores."""

    __tablename__ = "risk_scores"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    component_scores = Column(JSONB, nullable=True)
    scoring_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    triggered_by: Mapped[Optional[int]] = mapped_column(BIGINT, nullable=True)
    decay_factor: Mapped[Optional[float]] = mapped_column(Float, default=0.95)


class ScoringConfig(Base):
    """Scoring configuration per anomaly type."""

    __tablename__ = "scoring_config"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anomaly_type: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    base_weight: Mapped[float] = mapped_column(Float, default=1.0)
    z_score_threshold: Mapped[float] = mapped_column(Float, default=3.0)
    severity_mapping = Column(JSONB, nullable=True)
    decay_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    decay_factor: Mapped[Optional[float]] = mapped_column(Float, default=0.95)
    cooldown_minutes: Mapped[Optional[int]] = mapped_column(Integer, default=60)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class BehaviorBaseline(Base):
    """Behavior baselines hypertable — rolling stats per entity metric."""

    __tablename__ = "behavior_baselines"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    baseline_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    baseline_stddev: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    z_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_threshold: Mapped[Optional[float]] = mapped_column(Float, default=3.0)
    window_start = Column(DateTime(timezone=True), nullable=True)
    window_end = Column(DateTime(timezone=True), nullable=True)


class AnomalyDetection(Base):
    """Anomaly detections hypertable — detected anomalies with context."""

    __tablename__ = "anomaly_detections"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    anomaly_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    score: Mapped[float] = mapped_column(Float, nullable=False)
    z_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence = Column(JSONB, nullable=True)
    mitre_technique: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mitre_tactic: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    assigned_to: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
