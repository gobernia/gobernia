import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_theme import BoardTheme
from app.services.governance.default_themes import DEFAULT_THEMES


async def seed_default_themes(db: AsyncSession, annual_plan_id: uuid.UUID) -> int:
    """Siembra el catálogo por defecto si el plan aún no tiene temas.
    Idempotente. Devuelve cuántos temas insertó."""
    existing = await db.execute(
        select(BoardTheme.id).where(BoardTheme.annual_plan_id == annual_plan_id).limit(1)
    )
    if existing.first() is not None:
        return 0
    for i, t in enumerate(DEFAULT_THEMES):
        db.add(BoardTheme(
            annual_plan_id=annual_plan_id,
            key=t["key"], label=t["label"], type=t["type"],
            every_n_sessions=t["every_n_sessions"],
            is_default=True, active=True, order_index=i,
        ))
    await db.flush()
    return len(DEFAULT_THEMES)
