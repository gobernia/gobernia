"""Añade la columna owner_email a action_tasks SIN Alembic (ALTER idempotente).
    - owner_email : VARCHAR con el correo del responsable de la tarea.
      Habilita enviarle un enlace mágico a sus tareas (fase siguiente).

USO (solo con autorización humana — toca la DB):
    venv/bin/python -m scripts.alter_task_owner_email
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine

_SQL = [
    "ALTER TABLE action_tasks ADD COLUMN IF NOT EXISTS owner_email VARCHAR",
]


async def main():
    async with engine.begin() as conn:
        for sql in _SQL:
            await conn.execute(text(sql))
    await engine.dispose()
    print("OK: action_tasks.owner_email")


if __name__ == "__main__":
    asyncio.run(main())
