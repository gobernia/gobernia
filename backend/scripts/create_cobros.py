"""Crea las tablas de cobros (planes, cupones, canjes, suscripciones, pagos) SIN Alembic
(prod aplica esquema con create_all) y las cierra al acceso directo de Supabase igual que
el resto: RLS activo y sin permisos para anon/authenticated (ver docs/supabase-rls.md).
Idempotente. Todo en una transacción: si algo falla, no queda nada a medias.
USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.create_cobros
"""
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
import app.models  # noqa: F401  (registra todos los modelos en Base.metadata)
from app.models import Base

TABLAS = ("planes_suscripcion", "cupones", "suscripciones", "cupon_canjes", "pagos")


async def main():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool,
                                 connect_args={"statement_cache_size": 0})
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: Base.metadata.create_all(
                c, tables=[Base.metadata.tables[t] for t in TABLAS]))
            for t in TABLAS:
                await conn.execute(text(f'ALTER TABLE public."{t}" ENABLE ROW LEVEL SECURITY'))
                await conn.execute(text(f'REVOKE ALL PRIVILEGES ON TABLE public."{t}" FROM PUBLIC, anon, authenticated'))
                rls = await conn.scalar(text("SELECT relrowsecurity FROM pg_class WHERE oid = to_regclass(:t)"),
                                        {"t": f"public.{t}"})
                if rls is not True:
                    raise RuntimeError(f"RLS no quedó activo en {t}.")
                print(f"OK public.{t}: creada, RLS activo, sin acceso para anon/authenticated")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
