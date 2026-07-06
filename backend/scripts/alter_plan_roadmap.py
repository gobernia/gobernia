"""Añade la columna annual_plans.roadmap SIN Alembic (prod aplica esquema con ALTER idempotente).
USO (solo con autorización humana — toca la DB):
    venv/bin/python -m scripts.alter_plan_roadmap
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine


async def main():
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE annual_plans ADD COLUMN IF NOT EXISTS roadmap JSONB"))
    await engine.dispose()
    print("OK: columna annual_plans.roadmap")


if __name__ == "__main__":
    asyncio.run(main())
