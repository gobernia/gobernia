"""Añade board_sessions.conclusion (la conclusión ÚNICA del Consejo) SIN Alembic.
ALTER idempotente. Las sesiones viejas quedan con conclusion = NULL: el frontend cae a las
cuatro tarjetas de agent_analyses. No se migra nada.

USO (solo con autorización humana — toca la DB):
    venv/bin/python -m scripts.alter_board_conclusion
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine

_SQL = [
    "ALTER TABLE board_sessions ADD COLUMN IF NOT EXISTS conclusion JSONB",
]


async def main():
    async with engine.begin() as conn:
        for sql in _SQL:
            await conn.execute(text(sql))
    await engine.dispose()
    print("OK: board_sessions.conclusion")


if __name__ == "__main__":
    asyncio.run(main())
