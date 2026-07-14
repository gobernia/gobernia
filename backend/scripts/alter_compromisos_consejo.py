"""Extiende `compromisos` para los ACUERDOS DEL CONSEJO, SIN Alembic. ALTER idempotente.

    - board_session_id : de qué sesión de consejo nació el acuerdo (FK, indexado)
    - prioridad        : alta | media | baja  (default 'media')
    - pilar            : el vínculo con el Roadmap (nombre exacto del pilar; NULL/'' si es transversal)
    - racional         : por qué el Consejo lo acordó
    - responsable_email pasa a NULLABLE: la IA propone un ROL, el dueño pone el correo después.

USO (solo con autorización humana — toca la DB):
    venv/bin/python -m scripts.alter_compromisos_consejo
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine

_SQL = [
    "ALTER TABLE compromisos ADD COLUMN IF NOT EXISTS board_session_id UUID",
    # La FK se añade aparte: ADD CONSTRAINT no acepta IF NOT EXISTS en Postgres,
    # así que se hace condicional sobre pg_constraint.
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'compromisos_board_session_id_fkey'
        ) THEN
            ALTER TABLE compromisos
                ADD CONSTRAINT compromisos_board_session_id_fkey
                FOREIGN KEY (board_session_id) REFERENCES board_sessions(id) ON DELETE CASCADE;
        END IF;
    END $$;
    """,
    "CREATE INDEX IF NOT EXISTS ix_compromisos_board_session_id ON compromisos (board_session_id)",
    "ALTER TABLE compromisos ADD COLUMN IF NOT EXISTS prioridad VARCHAR(10) NOT NULL DEFAULT 'media'",
    "ALTER TABLE compromisos ADD COLUMN IF NOT EXISTS pilar VARCHAR",
    "ALTER TABLE compromisos ADD COLUMN IF NOT EXISTS racional TEXT",
    "ALTER TABLE compromisos ALTER COLUMN responsable_email DROP NOT NULL",
]


async def main():
    async with engine.begin() as conn:
        for sql in _SQL:
            await conn.execute(text(sql))
    await engine.dispose()
    print("OK: compromisos.board_session_id + prioridad + pilar + racional; responsable_email nullable")


if __name__ == "__main__":
    asyncio.run(main())
