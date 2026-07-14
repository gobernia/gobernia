"""Crea la tabla roadmap_versions SIN Alembic (prod aplica esquema con create_all).
Idempotente: create_all omite tablas existentes.

USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.create_roadmap_versions
"""
import asyncio

from app.db.session import engine
import app.models  # noqa: F401  (registra todos los modelos en Base.metadata)
from app.models import Base
from app.models.roadmap_version import RoadmapVersion


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[RoadmapVersion.__table__])
    await engine.dispose()
    print("OK: tabla roadmap_versions creada")


if __name__ == "__main__":
    asyncio.run(main())
