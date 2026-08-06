"""Crea un usuario en Supabase Auth (auth.users + auth.identities) directo en la BD.

Se usa para armar cuentas de DEMO sin pasar por el signup real. Copia la estructura
EXACTA de un usuario que ya funciona (aud/role/metadata) y hashea la contraseña con
bcrypt (lo que espera GoTrue). Los campos de token de texto van en '' (no NULL) para
evitar errores de escaneo de GoTrue al iniciar sesión.

Uso:  PYTHONPATH=. venv/bin/python scripts/create_auth_user.py <email> <password>
Idempotente: si el correo ya existe, no hace nada.
"""
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import text

from app.db.session import AsyncSessionLocal

INSTANCE_ID = "00000000-0000-0000-0000-000000000000"


async def create_user(email: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        exists = await db.execute(
            text("SELECT id FROM auth.users WHERE email = :e"), {"e": email}
        )
        if exists.fetchone():
            print(f"⚠️  Ya existe un usuario con {email!r}. No se hace nada.")
            return

        uid = uuid.uuid4()
        iid = uuid.uuid4()
        now = datetime.now(timezone.utc)
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode()

        app_meta = {"provider": "email", "providers": ["email"]}
        user_meta = {"sub": str(uid), "email": email, "email_verified": True, "phone_verified": False}

        await db.execute(text("""
            INSERT INTO auth.users (
                instance_id, id, aud, role, email, encrypted_password,
                email_confirmed_at, created_at, updated_at,
                raw_app_meta_data, raw_user_meta_data,
                is_super_admin, is_sso_user, is_anonymous,
                confirmation_token, recovery_token, email_change_token_new, email_change,
                email_change_token_current, phone_change, phone_change_token,
                reauthentication_token, email_change_confirm_status
            ) VALUES (
                :instance_id, :id, 'authenticated', 'authenticated', :email, :pw,
                :now, :now, :now,
                :app_meta, :user_meta,
                false, false, false,
                '', '', '', '',
                '', '', '',
                '', 0
            )
        """), {
            "instance_id": INSTANCE_ID, "id": uid, "email": email, "pw": pw_hash,
            "now": now, "app_meta": json.dumps(app_meta), "user_meta": json.dumps(user_meta),
        })

        # OJO: auth.identities.email es una columna GENERADA (sale de identity_data->>'email'),
        # no se puede insertar directo.
        await db.execute(text("""
            INSERT INTO auth.identities (
                id, user_id, provider_id, provider, identity_data,
                last_sign_in_at, created_at, updated_at
            ) VALUES (
                :id, :user_id, :provider_id, 'email', :identity_data,
                :now, :now, :now
            )
        """), {
            "id": iid, "user_id": uid, "provider_id": str(uid),
            "identity_data": json.dumps(user_meta), "now": now,
        })

        await db.commit()
        print(f"✅ Usuario creado: {email}  (user_id={uid})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: create_auth_user.py <email> <password>")
        raise SystemExit(1)
    asyncio.run(create_user(sys.argv[1], sys.argv[2]))
