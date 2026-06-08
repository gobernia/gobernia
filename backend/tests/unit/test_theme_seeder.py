import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.governance.theme_seeder import seed_default_themes


def _db_no_existing():
    """db.execute(...).first() -> None  => no hay temas aún."""
    result = MagicMock()
    result.first.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


def _db_with_existing():
    result = MagicMock()
    result.first.return_value = ("some-id",)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_seeds_13_when_empty():
    db = _db_no_existing()
    n = await seed_default_themes(db, uuid.uuid4())
    assert n == 13
    assert db.add.call_count == 13


@pytest.mark.asyncio
async def test_idempotent_when_existing():
    db = _db_with_existing()
    n = await seed_default_themes(db, uuid.uuid4())
    assert n == 0
    db.add.assert_not_called()
