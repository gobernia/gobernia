"""Agrega action_tasks.validacion SIN Alembic. Idempotente.
USO (solo con autorización — toca la DB): venv/bin/python -m scripts.alter_action_task_validacion"""
import asyncio
from sqlalchemy import text
from app.db.session import engine
import app.models  # noqa: F401
from app.models import Base


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE action_tasks ADD COLUMN IF NOT EXISTS validacion JSONB"))
    await engine.dispose()
    print("OK: columna validacion agregada a action_tasks")


if __name__ == "__main__":
    asyncio.run(main())
