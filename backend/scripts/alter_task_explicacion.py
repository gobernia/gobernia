"""Agrega action_tasks.explicacion SIN Alembic. Idempotente.
USO (solo con autorización — toca la DB): venv/bin/python -m scripts.alter_task_explicacion"""
import asyncio
from sqlalchemy import text
from app.db.session import engine
import app.models  # noqa: F401
from app.models import Base


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE action_tasks ADD COLUMN IF NOT EXISTS explicacion JSONB"))
    await engine.dispose()
    print("OK: columna explicacion agregada a action_tasks")


if __name__ == "__main__":
    asyncio.run(main())
