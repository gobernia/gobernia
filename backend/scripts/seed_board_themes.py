"""Backfill: siembra los Temas del Consejo por defecto en planes existentes.
Idempotente (no duplica si el plan ya tiene temas).

USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.seed_board_themes --all
    venv/bin/python -m scripts.seed_board_themes <annual_plan_id>
"""
import asyncio
import sys

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.annual_plan import AnnualPlan
from app.services.governance.theme_seeder import seed_default_themes


async def main(arg: str):
    async with AsyncSessionLocal() as db:
        if arg == "--all":
            res = await db.execute(select(AnnualPlan.id))
            ids = [row[0] for row in res.all()]
        else:
            ids = [arg]
        total = 0
        for pid in ids:
            n = await seed_default_themes(db, pid)
            total += n
            print(f"plan {pid}: +{n} temas")
        await db.commit()
        print(f"OK: {total} temas sembrados en {len(ids)} plan(es)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("USO: python -m scripts.seed_board_themes <annual_plan_id|--all>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
