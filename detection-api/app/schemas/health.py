"""Pydantic schemas for health and stats endpoints."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response schema for health check."""

    status: str
    module: str
    version: str
    db_connected: bool


class StatsResponse(BaseModel):
    """Response schema for event statistics."""

    total_events: int
    by_source: list[dict]
    by_entity: list[dict]
