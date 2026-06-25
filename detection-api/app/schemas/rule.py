"""Pydantic schemas for Rule Engine — simplified types."""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class RuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    conditions: dict = Field(
        default_factory=lambda: {"logic": "AND", "conditions": []},
        description="Rule conditions with AND/OR logic",
    )
    action: dict = Field(
        default_factory=lambda: {
            "type": "create_alert",
            "severity": "medium",
            "title": "",
            "description": "",
        },
        description="Rule action configuration",
    )
    enabled: bool = True
    priority: int = 0


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[dict] = None
    action: Optional[dict] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None


class RuleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    conditions: dict
    action: dict
    enabled: bool
    priority: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RuleListResponse(BaseModel):
    data: list[RuleResponse]
    total: int
    page: int
    limit: int
    total_pages: int
