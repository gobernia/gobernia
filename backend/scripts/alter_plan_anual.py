"""Añade la columna plan_anual a annual_plans SIN Alembic (ALTER idempotente).
    - plan_anual : JSONB con las 3-5 prioridades aprobadas del roadmap para el año en curso.
      Shape: {"anio", "aprobado", "aprobado_at", "pilares": [ {indice, nombre, ...} ]}

USO (solo con autorización humana — toca la DB):
    venv/bin/python -m scripts.alter_plan_anual
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine

_SQL = [
    "ALTER TABLE annual_plans ADD COLUMN IF NOT EXISTS plan_anual JSONB",
]


async def main():
    async with engine.begin() as conn:
        for sql in _SQL:
            await conn.execute(text(sql))
    await engine.dispose()
    print("OK: annual_plans.plan_anual")


if __name__ == "__main__":
    asyncio.run(main())
