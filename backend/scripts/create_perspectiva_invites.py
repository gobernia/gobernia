"""Crea la tabla perspectiva_invites SIN Alembic (prod aplica esquema con create_all).
Idempotente: create_all omite tablas existentes.
USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.create_perspectiva_invites
"""
import asyncio

from app.db.session import engine
import app.models  # noqa: F401  (registra todos los modelos en Base.metadata)
from app.models import Base


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("OK: tabla perspectiva_invites creada")


if __name__ == "__main__":
    asyncio.run(main())
