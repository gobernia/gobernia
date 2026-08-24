"""Añade la columna incluida a action_tasks SIN Alembic (ALTER idempotente).
    - incluida : BOOLEAN NOT NULL DEFAULT true. False = la tarea quedó FUERA del
      Plan anual aprobado: no se ejecuta ni cuenta para el avance, pero sigue
      visible como pendiente (activable o eliminable después).

USO (solo con autorización humana — toca la DB):
    venv/bin/python -m scripts.alter_action_task_incluida
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine

_SQL = [
    "ALTER TABLE action_tasks ADD COLUMN IF NOT EXISTS incluida BOOLEAN NOT NULL DEFAULT true",
]


async def main():
    async with engine.begin() as conn:
        for sql in _SQL:
            await conn.execute(text(sql))
    await engine.dispose()
    print("OK: action_tasks.incluida")


if __name__ == "__main__":
    asyncio.run(main())
