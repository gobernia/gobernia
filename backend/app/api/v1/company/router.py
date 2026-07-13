"""Logo de la empresa del cliente.

- POST   /company/logo  (multipart) → sube/reemplaza el logo. Devuelve la data URL.
- GET    /company/logo              → {has_logo, logo: data URL | null}
- DELETE /company/logo              → {has_logo: false}

Devolvemos data URL (no bytes crudos) porque el frontend llama con axios + header
de auth y no puede meter un endpoint autenticado directamente en un <img src>.
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.company.service import (
    LogoError, get_logo, get_logo_data_url, normalize_logo, to_data_url, upsert_logo,
)
from app.core.dependencies import get_current_user_id, get_db

router = APIRouter()


@router.post("/company/logo")
async def upload_logo(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    raw = await file.read()
    try:
        png = normalize_logo(raw, file.filename)
    except LogoError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    row = await upsert_logo(user_id, png, db)
    await db.commit()
    return {"has_logo": True, "logo": to_data_url(row.data, row.content_type)}


@router.get("/company/logo")
async def read_logo(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    data_url = await get_logo_data_url(user_id, db)
    return {"has_logo": data_url is not None, "logo": data_url}


@router.delete("/company/logo")
async def delete_logo(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    row = await get_logo(user_id, db)
    if row is not None:
        await db.delete(row)
        await db.commit()
    return {"has_logo": False}
