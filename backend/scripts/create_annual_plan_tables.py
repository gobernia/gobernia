"""Crea las tablas del plan anual y altera action_tasks SIN Alembic.
Idempotente: create_all omite tablas existentes; los ALTER usan IF NOT EXISTS / IF EXISTS.

USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.create_annual_plan_tables
"""
import asyncio
from sqlalchemy import text
from app.db.session import engine
import app.models  # noqa: F401  (registra todos los modelos en Base.metadata)
from app.models import Base


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE action_tasks ALTER COLUMN plan_id DROP NOT NULL"))
        await conn.execute(text(
            "ALTER TABLE action_tasks ADD COLUMN IF NOT EXISTS objective_id "
            "UUID REFERENCES objectives(id) ON DELETE CASCADE"))
        await conn.execute(text("ALTER TABLE action_tasks ADD COLUMN IF NOT EXISTS kpi_ref VARCHAR"))
    await engine.dispose()
    print("OK: tablas del plan anual creadas / action_tasks alterada")


if __name__ == "__main__":
    asyncio.run(main())
