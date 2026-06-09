"""Agrega la columna monthly_plans.covered_themes SIN Alembic (prod usa ALTER directo).
Idempotente (IF NOT EXISTS).

USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.add_covered_themes_column
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine


async def main():
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE monthly_plans ADD COLUMN IF NOT EXISTS covered_themes JSONB DEFAULT '[]'::jsonb"
        ))
    await engine.dispose()
    print("OK: columna monthly_plans.covered_themes creada")


if __name__ == "__main__":
    asyncio.run(main())
