"""Agrega columnas para el plan a N años SIN Alembic (prod usa create_all + ALTER).
Idempotente: ADD COLUMN IF NOT EXISTS.
USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.alter_plan_3anios
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine
import app.models  # noqa: F401
from app.models import Base


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "ALTER TABLE annual_plans ADD COLUMN IF NOT EXISTS horizon_years INTEGER NOT NULL DEFAULT 3"))
        await conn.execute(text(
            "ALTER TABLE annual_plans ADD COLUMN IF NOT EXISTS milestones JSONB"))
        await conn.execute(text(
            "ALTER TABLE action_tasks ADD COLUMN IF NOT EXISTS required_doc TEXT"))
    await engine.dispose()
    print("OK: columnas del plan a 3 años agregadas")


if __name__ == "__main__":
    asyncio.run(main())
