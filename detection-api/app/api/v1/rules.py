"""API v1 Custom Rules endpoints — CRUD for Rule Engine."""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.rule import CustomRule
from app.schemas.rule import (
    RuleCreate,
    RuleUpdate,
    RuleResponse,
    RuleListResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/rules", tags=["Custom Rules"])


@router.get("", response_model=RuleListResponse)
async def list_rules(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    enabled: Optional[bool] = None,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """List all custom rules with pagination."""
    # Count total
    count_q = select(func.count(CustomRule.id))
    if enabled is not None:
        count_q = count_q.where(CustomRule.enabled == enabled)
    total = (await session.execute(count_q)).scalar() or 0

    # Fetch page
    offset = (page - 1) * limit
    query = (
        select(CustomRule)
        .order_by(CustomRule.priority.desc(), CustomRule.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if enabled is not None:
        query = query.where(CustomRule.enabled == enabled)

    result = await session.execute(query)
    rules = result.scalars().all()

    total_pages = max(1, (total + limit - 1) // limit)

    return {
        "data": [RuleResponse.model_validate(r) for r in rules],
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }


@router.post("", response_model=RuleResponse, status_code=201)
async def create_rule(
    payload: RuleCreate,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Create a new custom rule."""
    rule = CustomRule(
        name=payload.name,
        description=payload.description,
        conditions=payload.conditions or {},
        action=payload.action or {},
        enabled=payload.enabled,
        priority=payload.priority,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)

    logger.info("Created custom rule id=%s name='%s'", rule.id, rule.name)
    return RuleResponse.model_validate(rule).model_dump()


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get a single custom rule by ID."""
    result = await session.execute(
        select(CustomRule).where(CustomRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    return RuleResponse.model_validate(rule).model_dump()


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: int,
    payload: RuleUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Update an existing custom rule (partial update)."""
    result = await session.execute(
        select(CustomRule).where(CustomRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "name" in update_data:
        rule.name = update_data["name"]
    if "description" in update_data:
        rule.description = update_data["description"]
    if "conditions" in update_data and update_data["conditions"] is not None:
        rule.conditions = update_data["conditions"]
    if "action" in update_data and update_data["action"] is not None:
        rule.action = update_data["action"]
    if "enabled" in update_data:
        rule.enabled = update_data["enabled"]
    if "priority" in update_data:
        rule.priority = update_data["priority"]

    rule.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(rule)

    logger.info("Updated custom rule id=%s name='%s'", rule.id, rule.name)
    return RuleResponse.model_validate(rule).model_dump()


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a custom rule."""
    result = await session.execute(
        select(CustomRule).where(CustomRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    await session.delete(rule)
    await session.commit()

    logger.info("Deleted custom rule id=%s name='%s'", rule.id, rule.name)
