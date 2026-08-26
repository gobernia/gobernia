"""Añade a action_tasks los campos de agenda de gobierno SIN Alembic (ALTER idempotente).
    - lead_agent        : VARCHAR(20)  — consejero IA que lidera el punto (CFO|CSO|CRO|Auditor).
    - agenda_type       : VARCHAR(20)  — informacion | seguimiento | deliberacion | decision.
    - decision_expected : TEXT         — decisión/recomendación esperada de la sesión.

Cada "tarea" es funcionalmente un punto del Orden del Día del Consejo
(revisión del cliente experto — ver PROMPTS-CONSEJEROS-GOBERNIA.md).

USO (solo con autorización humana — toca la DB):
    venv/bin/python -m scripts.alter_action_task_agenda
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine

_SQL = [
    "ALTER TABLE action_tasks ADD COLUMN IF NOT EXISTS lead_agent VARCHAR(20)",
    "ALTER TABLE action_tasks ADD COLUMN IF NOT EXISTS agenda_type VARCHAR(20)",
    "ALTER TABLE action_tasks ADD COLUMN IF NOT EXISTS decision_expected TEXT",
]


async def main():
    async with engine.begin() as conn:
        for sql in _SQL:
            await conn.execute(text(sql))
    await engine.dispose()
    print("OK: action_tasks.lead_agent / agenda_type / decision_expected")


if __name__ == "__main__":
    asyncio.run(main())
