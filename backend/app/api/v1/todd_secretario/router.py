"""Todd secretario — chat permanente que conoce el tablero, el Roadmap y los acuerdos.

GET  /todd-secretario/mensajes  → historial del chat de Todd secretario del usuario.
POST /todd-secretario/mensajes  → un turno: arma contexto, llama a Todd, persiste y responde.

Reusa ChatMessage con el discriminador agent="todd_secretario" (sin columnas nuevas).
La accion "proponer_cambio" se resuelve aquí llamando a `adapt_task`; el "Reemplazar" lo
hace el frontend con el PATCH /tasks/{id} que ya existe (por eso devolvemos title/description).
"""
import uuid

import anyio
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id, get_db
from app.models.chat_message import ChatMessage
from app.services.ai.task_adapter import adapt_task
from app.services.ai.todd_secretario import run_todd_secretario_turn
from app.api.v1.todd_secretario.service import (
    TODD_SECRETARIO_AGENT,
    build_contexto,
    get_anchor_board_session_id,
)
# Reutilizamos la verificación de propiedad y el contexto de empresa del router de tareas
# (no lo modificamos, solo importamos).
from app.api.v1.action_plans.router import (
    _get_user_task_or_404,
    _objetivo_empresa,
    _empresa_ctx,
)

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ToddSecretarioIn(BaseModel):
    content: str


class ToddMensajeOut(BaseModel):
    message_id: str
    role: str
    content: str
    created_at: object | None = None


class ToddSecretarioOut(BaseModel):
    reply: str
    accion: dict | None = None


# ── GET /todd-secretario/mensajes ─────────────────────────────────────────────

@router.get("/todd-secretario/mensajes", response_model=list[ToddMensajeOut])
async def listar_mensajes(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.user_id == user_id,
            ChatMessage.agent == TODD_SECRETARIO_AGENT,
        )
        .order_by(ChatMessage.created_at)
    )).scalars().all()
    return [
        ToddMensajeOut(
            message_id=str(m.id),
            role=m.role,
            content=m.content,
            created_at=m.created_at,
        )
        for m in rows
    ]


# ── POST /todd-secretario/mensajes ────────────────────────────────────────────

@router.post("/todd-secretario/mensajes", response_model=ToddSecretarioOut)
async def enviar_mensaje(
    body: ToddSecretarioIn,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    anchor_id = await get_anchor_board_session_id(user_id, db)
    contexto = await build_contexto(user_id, db)

    # Historial previo del chat de Todd secretario (para continuidad).
    history_rows = (await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.user_id == user_id,
            ChatMessage.agent == TODD_SECRETARIO_AGENT,
        )
        .order_by(ChatMessage.created_at)
    )).scalars().all()
    mensajes = [{"role": m.role, "content": m.content} for m in history_rows]
    mensajes.append({"role": "user", "content": body.content})

    # Turno de Todd (llamada de red → hilo aparte para no bloquear el event loop).
    turn = await anyio.to_thread.run_sync(
        lambda: run_todd_secretario_turn(mensajes, contexto)
    )
    reply = turn.get("reply") or ""
    accion = turn.get("accion")

    # Si Todd propone cambiar una tarea, la resolvemos: verificamos propiedad (404 si no
    # es del usuario) y generamos la alternativa con adapt_task.
    accion_out: dict | None = None
    if accion and accion.get("tipo") == "proponer_cambio":
        accion_out = await _resolver_propuesta(accion, user_id, db)

    # Persistir el turno (usuario + Todd), anclado a la sesión de consejo más reciente.
    if anchor_id is not None:
        db.add(ChatMessage(
            board_session_id=anchor_id, user_id=user_id,
            role="user", agent=TODD_SECRETARIO_AGENT, content=body.content,
        ))
        db.add(ChatMessage(
            board_session_id=anchor_id, user_id=user_id,
            role="assistant", agent=TODD_SECRETARIO_AGENT, content=reply,
            message_metadata={"accion": accion_out} if accion_out else None,
        ))
        await db.flush()
        await db.commit()

    return ToddSecretarioOut(reply=reply, accion=accion_out)


async def _resolver_propuesta(accion: dict, user_id: str, db: AsyncSession) -> dict | None:
    """Verifica propiedad de la tarea (404 si no es del usuario) y arma la propuesta
    de alternativa con adapt_task. Un task_id inválido/inexistente se ignora (sin accion)."""
    raw_id = str(accion.get("task_id") or "").strip()
    try:
        task_uuid = uuid.UUID(raw_id)
    except (ValueError, TypeError):
        return None

    # Lanza HTTPException 404 si la tarea no es del usuario.
    task = await _get_user_task_or_404(task_uuid, user_id, db)

    objetivo, _ = await _objetivo_empresa(task, user_id, db)
    empresa_ctx = await _empresa_ctx(user_id, db)
    motivo = str(accion.get("motivo") or "").strip()
    data = await anyio.to_thread.run_sync(
        lambda: adapt_task(task.title, objetivo, empresa_ctx, motivo)
    )
    return {
        "tipo": "proponer_cambio",
        "task_id": str(task.id),
        "propuesta": {
            "title": data["nueva_tarea"],
            "description": data["descripcion"],
            "por_que": data["por_que"],
        },
    }
