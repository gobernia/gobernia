"""
Siembra un OnboardingSession COMPLETO (8 etapas + KPIs + visión) para un usuario EXISTENTE
de Supabase Auth, identificado por su correo. Así la cuenta queda "onboarding completo" y solo
falta generar el plan en la app y subir documentos de evidencia.

NO crea el usuario de login (eso se hace registrándose en la app). Solo busca su id en
auth.users por correo e inyecta/repone su onboarding.

USO (desde backend/):
    venv/bin/python -m scripts.seed_onboarding_demo correo@ejemplo.com

OJO: usa el DATABASE_URL configurado (apunta a PROD). Correr solo con autorización.
"""
import asyncio
import sys
from datetime import datetime, timezone

from sqlalchemy import delete, select, text

from app.db.session import AsyncSessionLocal
from app.models.onboarding_session import OnboardingSession

GOVERNANCE_SCORE = 58

MEMORY_BUFFER = {
    "company": {
        "name": "Keting Media",
        "industry": "Desarrollo de apps y plataformas digitales",
        "employees": 40,
        "annual_revenue": "30,000,000 MXN",
        "years_operating": 8,
        "has_board": False,
        "is_family_business": True,
        "website": "https://www.ketingmedia.com",
        "competitors": ["Wizeline", "Neoris", "Globant", "Magokoro", "Indigo Technologies"],
    },
    "vision": {
        "statement": (
            "Ser un referente en México en el desarrollo de apps y plataformas digitales "
            "robustas, duplicando ingresos en 3 años con rentabilidad sana, clientes "
            "diversificados y un gobierno corporativo profesional."
        )
    },
    "governance": {"score": GOVERNANCE_SCORE, "level": "En desarrollo"},
    "kpis": {
        "financieros": [
            {"label": "Margen neto", "current_value": 6, "benchmark": 11, "unit": "%",
             "alert": "Por debajo de meta"},
            {"label": "Razón corriente", "current_value": 1.1, "benchmark": 1.8, "unit": "x",
             "alert": ""},
        ],
        "comerciales": [
            {"label": "Crecimiento de ventas", "current_value": 4, "benchmark": 15, "unit": "%",
             "alert": ""},
            {"label": "Concentración de clientes (top 3)", "current_value": 55, "benchmark": 30,
             "unit": "%", "alert": "Riesgo de concentración"},
        ],
        "operativos": [
            {"label": "Rotación de personal", "current_value": 22, "benchmark": 12, "unit": "%",
             "alert": ""},
        ],
    },
    "ai_context": {
        "company_narrative": (
            "Keting Media es una empresa que desarrolla apps y plataformas digitales robustas para "
            "sus clientes. Con 8 años de operación, buen portafolio técnico pero márgenes apretados "
            "y alta dependencia de pocos clientes grandes. Busca profesionalizar su gobierno "
            "corporativo, diversificar clientes y mejorar rentabilidad."
        )
    },
}


async def main(email: str) -> None:
    async with AsyncSessionLocal() as db:
        # 1) Buscar el user_id real en Supabase Auth por correo.
        res = await db.execute(text("SELECT id FROM auth.users WHERE email = :email"), {"email": email})
        row = res.first()
        if not row:
            print(f"❌ No existe un usuario en auth.users con el correo {email!r}. "
                  f"Regístrate primero en la app con ese correo y vuelve a correr el script.")
            return
        user_id = str(row[0])

        # 2) Reponer onboarding previo del usuario (idempotente).
        await db.execute(delete(OnboardingSession).where(OnboardingSession.user_id == user_id))

        # 3) Insertar onboarding completo.
        sess = OnboardingSession(
            user_id=user_id,
            completed_stages=[1, 2, 3, 4, 5, 6, 7, 8],
            memory_buffer=MEMORY_BUFFER,
            governance_score=GOVERNANCE_SCORE,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(sess)
        await db.commit()
        print(f"✅ Onboarding completo sembrado para {email} (user_id={user_id}).")
        print("   Ahora entra a la app → Plan → Generar plan → sube el documento de una tarea.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: venv/bin/python -m scripts.seed_onboarding_demo correo@ejemplo.com")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
