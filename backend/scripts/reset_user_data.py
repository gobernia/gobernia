"""
Borra TODOS los datos de la app para un usuario (identificado por su correo de Supabase Auth),
dejándolo "como recién registrado": sin onboarding, sin Todd, sin diagnóstico, sin FODA,
sin plan, sin sesiones de consejo, sin documentos/evidencias ni compromisos.

NO toca auth.users: la cuenta de login se conserva. Solo limpia las tablas de la aplicación.

Borra en orden hijo→padre (no depende de que existan cascadas en prod) y dentro de UNA
transacción: o se borra todo o no se borra nada. Reporta cuántas filas borró por tabla.

USO (desde backend/):
    venv/bin/python -m scripts.reset_user_data correo@ejemplo.com

OJO: usa el DATABASE_URL configurado (apunta a PROD). Correr SOLO con autorización humana.
"""
import asyncio
import sys

from sqlalchemy import text

from app.db.session import AsyncSessionLocal

# (etiqueta, SQL). Orden hijo→padre. Todas parametrizadas por :uid.
_STEPS = [
    ("evidences", """
        DELETE FROM evidences
        WHERE action_task_id IN (
            SELECT t.id FROM action_tasks t
            LEFT JOIN action_plans ap ON ap.id = t.plan_id
            LEFT JOIN objectives o ON o.id = t.objective_id
            LEFT JOIN monthly_plans mp ON mp.id = o.monthly_plan_id
            LEFT JOIN annual_plans an ON an.id = mp.annual_plan_id
            WHERE ap.user_id = :uid OR an.user_id = :uid
        )
    """),
    ("action_tasks", """
        DELETE FROM action_tasks t
        WHERE t.plan_id IN (SELECT id FROM action_plans WHERE user_id = :uid)
           OR t.objective_id IN (
                SELECT o.id FROM objectives o
                JOIN monthly_plans mp ON mp.id = o.monthly_plan_id
                JOIN annual_plans an ON an.id = mp.annual_plan_id
                WHERE an.user_id = :uid
           )
    """),
    ("objectives", """
        DELETE FROM objectives
        WHERE monthly_plan_id IN (
            SELECT mp.id FROM monthly_plans mp
            JOIN annual_plans an ON an.id = mp.annual_plan_id
            WHERE an.user_id = :uid
        )
    """),
    ("monthly_plans", """
        DELETE FROM monthly_plans
        WHERE annual_plan_id IN (SELECT id FROM annual_plans WHERE user_id = :uid)
    """),
    ("board_themes", """
        DELETE FROM board_themes
        WHERE annual_plan_id IN (SELECT id FROM annual_plans WHERE user_id = :uid)
    """),
    ("annual_plans", "DELETE FROM annual_plans WHERE user_id = :uid"),
    ("action_plans", "DELETE FROM action_plans WHERE user_id = :uid"),
    ("chat_messages", "DELETE FROM chat_messages WHERE user_id = :uid"),
    ("documents", "DELETE FROM documents WHERE user_id = :uid"),
    ("compromisos", "DELETE FROM compromisos WHERE user_id = :uid"),
    ("board_sessions", "DELETE FROM board_sessions WHERE user_id = :uid"),
    ("diagnosticos_estrategicos", "DELETE FROM diagnosticos_estrategicos WHERE user_id = :uid"),
    ("todd_sessions", "DELETE FROM todd_sessions WHERE user_id = :uid"),
    ("onboarding_sessions", "DELETE FROM onboarding_sessions WHERE user_id = :uid"),
]


async def main(email: str) -> None:
    async with AsyncSessionLocal() as db:
        res = await db.execute(text("SELECT id FROM auth.users WHERE email = :email"), {"email": email})
        row = res.first()
        if not row:
            print(f"❌ No existe un usuario en auth.users con el correo {email!r}.")
            return
        user_id = str(row[0])
        print(f"Usuario encontrado: {email} (user_id={user_id})")
        print("Borrando datos de la app (auth.users NO se toca)…\n")

        total = 0
        for label, sql in _STEPS:
            result = await db.execute(text(sql), {"uid": user_id})
            n = result.rowcount or 0
            total += n
            if n:
                print(f"  - {label:28s} {n} fila(s)")
        await db.commit()
        print(f"\n✅ Reset completo: {total} fila(s) borradas. {email} queda como recién registrado.")
        print("   La cuenta de login sigue activa: solo entra a la app y empieza con Todd.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: venv/bin/python -m scripts.reset_user_data correo@ejemplo.com")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
