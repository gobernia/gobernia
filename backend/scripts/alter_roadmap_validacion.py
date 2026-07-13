"""Añade el ciclo de validación del roadmap a annual_plans SIN Alembic (ALTER idempotente).
    - roadmap_status        : 'borrador' | 'validado'
    - roadmap_validated_at  : fecha de validación

USO (solo con autorización humana — toca la DB):
    venv/bin/python -m scripts.alter_roadmap_validacion
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine

_SQL = [
    "ALTER TABLE annual_plans ADD COLUMN IF NOT EXISTS roadmap_status VARCHAR(20) NOT NULL DEFAULT 'borrador'",
    "ALTER TABLE annual_plans ADD COLUMN IF NOT EXISTS roadmap_validated_at TIMESTAMPTZ",
]


async def main():
    async with engine.begin() as conn:
        for sql in _SQL:
            await conn.execute(text(sql))
    await engine.dispose()
    print("OK: annual_plans.roadmap_status + roadmap_validated_at")


if __name__ == "__main__":
    asyncio.run(main())
