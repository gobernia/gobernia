"""
Borra TODAS las cuentas (auth.users) y sus datos de app, EXCEPTO el correo que se pasa.
Deja la base como recién estrenada salvo por la cuenta que se conserva.

Uso: venv/bin/python -m scripts.purge_except info@ketingmedia.com

⚠️ DESTRUCTIVO E IRREVERSIBLE. Corre contra la base que apunte DATABASE_URL (PRODUCCIÓN).
Reusa los _STEPS de reset_user_data (datos de app) y además elimina la fila de auth.users
(cascada a auth.identities/sessions).
"""
import asyncio
import sys

from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from scripts.reset_user_data import _STEPS


async def main(keep_email: str) -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            text("SELECT id, email FROM auth.users WHERE email != :keep ORDER BY created_at"),
            {"keep": keep_email},
        )).all()

        keep = (await db.execute(
            text("SELECT count(*) FROM auth.users WHERE email = :keep"), {"keep": keep_email}
        )).scalar()
        if not keep:
            print(f"❌ ABORTA: no existe la cuenta a conservar {keep_email!r}. No se borra nada.")
            return

        print(f"Se conserva: {keep_email}")
        print(f"A borrar: {len(rows)} cuenta(s) + sus datos de app.\n")

        borradas = 0
        for uid, email in rows:
            uid = str(uid)
            app_rows = 0
            for _label, sql in _STEPS:
                r = await db.execute(text(sql), {"uid": uid})
                app_rows += r.rowcount or 0
            await db.execute(text("DELETE FROM auth.users WHERE id = :uid"), {"uid": uid})
            borradas += 1
            print(f"  ✗ {email:<32} (datos app: {app_rows} fila(s) + cuenta)")

        await db.commit()
        print(f"\n✅ Listo: {borradas} cuenta(s) borradas. Solo queda {keep_email}.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: venv/bin/python -m scripts.purge_except correo_a_conservar@ejemplo.com")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
