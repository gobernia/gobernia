"""
Router de agentes de IA.
Placeholder — se implementa en Etapa 9 (Dashboard del Consejo).
"""
from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user_id

router = APIRouter()


@router.get("/status")
async def agents_status(user_id: str = Depends(get_current_user_id)):
    return {
        "agents": ["CFO", "CRO", "CSO", "Auditor"],
        "status": "ready",
        "note": "Los agentes se activan al completar el onboarding",
    }
