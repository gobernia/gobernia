"""Añade la columna periodicidad a annual_plans SIN Alembic (ALTER idempotente).
    - periodicidad : VARCHAR(12) NOT NULL DEFAULT 'mensual'. Cada cuánto se reparten y
      revisan las tareas del plan: mensual | trimestral | semestral. Los planes existentes
      quedan en 'mensual' (su comportamiento de siempre).

USO (solo con autorización humana — toca la DB):
    venv/bin/python -m scripts.alter_plan_periodicidad
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine

_SQL = [
    "ALTER TABLE annual_plans ADD COLUMN IF NOT EXISTS periodicidad VARCHAR(12) NOT NULL DEFAULT 'mensual'",
]


async def main():
    async with engine.begin() as conn:
        for sql in _SQL:
            await conn.execute(text(sql))
    await engine.dispose()
    print("OK: annual_plans.periodicidad")


if __name__ == "__main__":
    asyncio.run(main())
