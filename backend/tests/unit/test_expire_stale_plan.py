from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.annual_plan.router import _expire_if_stale


@pytest.mark.asyncio
async def test_expira_generating_viejo():
    plan = MagicMock(); plan.status = "generating"
    plan.created_at = datetime.now(timezone.utc) - timedelta(minutes=45)
    db = AsyncMock()
    out = await _expire_if_stale(plan, db)
    assert out.status == "failed"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_expira_generating_reciente():
    plan = MagicMock(); plan.status = "generating"
    plan.created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db = AsyncMock()
    out = await _expire_if_stale(plan, db)
    assert out.status == "generating"
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_no_toca_active():
    plan = MagicMock(); plan.status = "active"
    plan.created_at = datetime.now(timezone.utc) - timedelta(days=2)
    db = AsyncMock()
    out = await _expire_if_stale(plan, db)
    assert out.status == "active"
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_plan_none():
    db = AsyncMock()
    assert await _expire_if_stale(None, db) is None
