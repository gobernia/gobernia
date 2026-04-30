"""
Router de documentos.
Placeholder — se implementa en Etapa 7.
"""
from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user_id

router = APIRouter()


@router.get("/status")
async def documents_status(user_id: str = Depends(get_current_user_id)):
    return {"status": "ready", "note": "Upload disponible en Etapa 7"}
