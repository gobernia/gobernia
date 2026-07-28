"""Añade la columna pilar_index a objectives SIN Alembic (ALTER idempotente).
    - pilar_index : INTEGER, el índice del pilar en roadmap["pilares"] que el
      objetivo hace avanzar (None si no se pudo determinar).

USO (solo con autorización humana — toca la DB):
    venv/bin/python -m scripts.alter_objective_pilar
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine

_SQL = [
    "ALTER TABLE objectives ADD COLUMN IF NOT EXISTS pilar_index INTEGER",
]


async def main():
    async with engine.begin() as conn:
        for sql in _SQL:
            await conn.execute(text(sql))
    await engine.dispose()
    print("OK: objectives.pilar_index")


if __name__ == "__main__":
    asyncio.run(main())
