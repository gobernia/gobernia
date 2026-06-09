"""Agrega la columna monthly_plans.chair_agenda SIN Alembic (prod usa ALTER directo).
Idempotente (IF NOT EXISTS).

USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.add_chair_agenda_column
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine


async def main():
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE monthly_plans ADD COLUMN IF NOT EXISTS chair_agenda JSONB"
        ))
    await engine.dispose()
    print("OK: columna monthly_plans.chair_agenda creada")


if __name__ == "__main__":
    asyncio.run(main())
