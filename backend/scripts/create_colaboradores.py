"""Crea la tabla colaboradores SIN Alembic (prod aplica esquema con create_all).
Idempotente: create_all omite tablas existentes.
USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.create_colaboradores
"""
import asyncio

from app.db.session import engine
import app.models  # noqa: F401  (registra todos los modelos en Base.metadata)
from app.models import Base
from app.models.colaborador import Colaborador


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn, tables=[Colaborador.__table__]
            )
        )
    await engine.dispose()
    print("OK: tabla colaboradores")


if __name__ == "__main__":
    asyncio.run(main())
