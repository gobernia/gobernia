"""Añade la columna chat a colaboradores SIN Alembic (ALTER idempotente).
    - chat : JSONB con el historial del chat de Todd para el responsable.
      Shape: lista de {"role", "content"}.

USO (solo con autorización humana — toca la DB):
    venv/bin/python -m scripts.alter_colaborador_chat
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine

_SQL = [
    "ALTER TABLE colaboradores ADD COLUMN IF NOT EXISTS chat JSONB",
]


async def main():
    async with engine.begin() as conn:
        for sql in _SQL:
            await conn.execute(text(sql))
    await engine.dispose()
    print("OK: colaboradores.chat")


if __name__ == "__main__":
    asyncio.run(main())
