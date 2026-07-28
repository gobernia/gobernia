"""Añade la columna acta_snapshot a board_sessions SIN Alembic (ALTER idempotente).
    - acta_snapshot : JSONB con la foto inmutable del acta de la sesión (cadena +
      periodo + fecha), congelada al primer descargue del acta de esa sesión.

USO (solo con autorización humana — toca la DB):
    venv/bin/python -m scripts.alter_board_session_acta
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine

_SQL = [
    "ALTER TABLE board_sessions ADD COLUMN IF NOT EXISTS acta_snapshot JSONB",
]


async def main():
    async with engine.begin() as conn:
        for sql in _SQL:
            await conn.execute(text(sql))
    await engine.dispose()
    print("OK: board_sessions.acta_snapshot")


if __name__ == "__main__":
    asyncio.run(main())
