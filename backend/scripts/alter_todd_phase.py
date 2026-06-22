"""Agrega la columna phase a todd_sessions SIN Alembic (prod usa create_all + ALTER).
Idempotente: ADD COLUMN IF NOT EXISTS.
USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.alter_todd_phase
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
            "ALTER TABLE todd_sessions ADD COLUMN IF NOT EXISTS phase VARCHAR(20) NOT NULL DEFAULT 'interno'"))
    await engine.dispose()
    print("OK: columna phase agregada a todd_sessions")


if __name__ == "__main__":
    asyncio.run(main())
