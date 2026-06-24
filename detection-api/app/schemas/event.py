"""Pydantic schemas for event ingestion endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class EventCreate(BaseModel):
    """Schema for a single event ingestion."""

    timestamp: Optional[datetime] = None
    hostname: Optional[str] = None
    source: Optional[str] = None
    source_ip: Optional[str] = None
    log_level: Optional[str] = None
    message: Optional[str] = None
    raw: Optional[dict] = None

    model_config = {"from_attributes": True}


class BatchEventCreate(BaseModel):
    """Schema for batch event ingestion (max 1000 events)."""

    events: list[EventCreate] = Field(..., min_length=1, max_length=1000)

    @field_validator("events")
    @classmethod
    def validate_batch_size(cls, v: list) -> list:
        if len(v) > 1000:
            raise ValueError("Batch size exceeds maximum of 1000 events")
        return v


class EventResponse(BaseModel):
    """Response schema after event ingestion."""

    id: int
    status: str
    source: str


class BatchEventResponse(BaseModel):
    """Response schema after batch event ingestion."""

    count: int
    status: str
    source: str
