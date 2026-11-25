"""
El Auditor del Consejo validando la EVIDENCIA de las tareas del periodo.

Al sesionar, cada responsable ha subido (o no) documentos que respaldan su tarea. Este servicio
actúa como el Auditor del órgano: lee esos documentos y dice, tarea por tarea, si REALMENTE
sustentan que la tarea se cumplió (`validada`), si cubren solo una parte real de lo pedido
(`parcial`) o si no bastan / no corresponden / no se pudieron leer (`insuficiente`). Además separa
lo que SÍ está (`cubre`), lo que falta (`falta`) y otra evidencia que también serviría
(`alternativas`): con eso Todd le explica al dueño qué hacer, en vez de solo decirle que falta.

Opus + tool-use forzado. Recibe, por tarea: {task_id, title, status, docs:[bloques multimodales]}.
Devuelve [{task_id, estado:"validada"|"parcial"|"insuficiente"|"sin_revisar", motivo,
cubre?, falta?, alternativas?}].

Reglas de blindaje (nunca tumban la sesión):
- Sin API key o con error del tool-use → todas las tareas con documentos quedan `sin_revisar`.
- Una tarea SIN documentos legibles → `insuficiente` sin gastar tokens.
- Cap duro de tareas por sesión y de bytes totales: el excedente queda `sin_revisar` con motivo,
  y se registra en log lo que no alcanzó a revisarse (no se trunca en silencio).
"""
import logging

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _build_company_context, _create_with_retry, _tool_input
from app.services.ai.modelos import pedir_herramienta
from app.services.ai.prompt_loader import load_prompt

_log = logging.getLogger(__name__)

VALIDACION_MAX_TOKENS = 2048

# Topes por sesión (acotan el costo). Las tareas se ordenan por recencia antes de aplicarlos.
MAX_TAREAS_POR_SESION = 12
MAX_BYTES_VALIDACION = 15 * 1024 * 1024  # ~20 MB en base64: margen bajo el corte de 32 MB de la API

_ESTADOS_VALIDOS = {"validada", "parcial", "insuficiente"}
MAX_ALTERNATIVAS = 3

_MOTIVO_SIN_DOCS = "No hay documentos legibles adjuntos; no se puede verificar el cumplimiento de la tarea."
_MOTIVO_SIN_REVISAR = "No se pudo revisar la evidencia con el Auditor en esta sesión."
_MOTIVO_EXCEDENTE = "No alcanzó a revisarse en esta sesión (se priorizaron las tareas más recientes)."
_MOTIVO_SIN_VEREDICTO = "El Auditor no emitió un veredicto para esta tarea."

VALIDACION_SYSTEM_PROMPT = load_prompt("validacion_evidencias")  # editable en backend/prompts/validacion_evidencias.md

VALIDACION_TOOL = {
    "name": "validar_evidencias",
    "description": "Entrega el veredicto del Auditor sobre la evidencia de cada tarea del periodo.",
    "input_schema": {
        "type": "object",
        "properties": {
            "validaciones": {
                "type": "array",
                "description": "Un veredicto por cada tarea evaluada.",
                "items": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "El id EXACTO de la tarea, copiado literal de la que se te dio.",
                        },
                        "estado": {
                            "type": "string",
                            "enum": ["validada", "parcial", "insuficiente"],
                            "description": ("validada = la evidencia sustenta el cumplimiento; parcial = "
                                            "demuestra una parte real de lo pedido, no todo; "
                                            "insuficiente = no basta."),
                        },
                        "motivo": {
                            "type": "string",
                            "description": "Por qué. Cita el documento si aplica. 1-2 oraciones.",
                        },
                        "documento": {
                            "type": "string",
                            "description": ("Qué es lo que se subió, en pocas palabras y en español (p. ej. "
                                            "«un currículum (CV) de una persona», «saldos bancarios al 23 de "
                                            "noviembre», «cotización de un sistema de inventarios»)."),
                        },
                        "otro_documento": {
                            "type": "boolean",
                            "description": ("true si lo que se subió es OTRO documento, que no tiene que ver "
                                            "con lo que pide la tarea (un CV, una foto personal, un archivo de "
                                            "otro tema). false si es del tema aunque no alcance."),
                        },
                        "cubre": {
                            "type": "string",
                            "description": ("Lo que SÍ muestran los documentos para esta tarea (qué documento, "
                                            "periodo, cifras clave). Vacío si no muestran nada útil."),
                        },
                        "falta": {
                            "type": "string",
                            "description": "Lo que falta para demostrar lo pedido. Vacío si está validada.",
                        },
                        "alternativas": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": ("1 a 3 documentos alternativos, realistas para una empresa "
                                            "mediana, que también demostrarían lo que falta. Vacío si "
                                            "está validada."),
                        },
                    },
                    "required": ["task_id", "estado", "motivo"],
                },
            },
        },
        "required": ["validaciones"],
    },
}


def _sin_revisar(task_id: str, motivo: str = _MOTIVO_SIN_REVISAR) -> dict:
    return {"task_id": str(task_id), "estado": "sin_revisar", "motivo": motivo}


def _insuficiente(task_id: str, motivo: str) -> dict:
    return {"task_id": str(task_id), "estado": "insuficiente", "motivo": motivo}


def _docs_bytes(docs: list[dict]) -> int:
    """Bytes crudos aproximados de los bloques base64 de una tarea (para el cap de tamaño)."""
    total = 0
    for b in docs or []:
        data = (b.get("source") or {}).get("data")
        if data:
            total += len(data) * 3 // 4
    return total


def validar_evidencias(tareas_con_docs: list[dict], memory_buffer: dict) -> list[dict]:
    """
    tareas_con_docs: [{task_id, title, status, docs:[bloques multimodales]}], ordenadas de la más
      reciente a la más antigua (para que el cap deje fuera las más viejas, no las nuevas).
    Devuelve [{task_id, estado, motivo}] con un veredicto por cada tarea recibida.
    """
    if not tareas_con_docs:
        return []

    # Tareas sin ningún documento legible: no se pueden verificar. No se gasta tokens en ellas.
    sin_docs = [t for t in tareas_con_docs if not t.get("docs")]
    con_docs = [t for t in tareas_con_docs if t.get("docs")]
    resultados: list[dict] = [_insuficiente(t["task_id"], _MOTIVO_SIN_DOCS) for t in sin_docs]

    if not con_docs:
        return resultados

    # Sin IA no se puede auditar: las tareas con documentos quedan sin_revisar (no revienta nada).
    if not settings.ANTHROPIC_API_KEY:
        return resultados + [_sin_revisar(t["task_id"]) for t in con_docs]

    # Cap duro: nº de tareas y bytes totales. El excedente queda sin_revisar (y se registra).
    seleccionadas: list[dict] = []
    excedente: list[dict] = []
    total_bytes = 0
    for t in con_docs:
        if len(seleccionadas) >= MAX_TAREAS_POR_SESION:
            excedente.append(t)
            continue
        tb = _docs_bytes(t["docs"])
        if seleccionadas and total_bytes + tb > MAX_BYTES_VALIDACION:
            excedente.append(t)
            continue
        seleccionadas.append(t)
        total_bytes += tb

    if excedente:
        _log.warning(
            "validación de evidencias: %d tarea(s) NO alcanzaron a revisarse por el cap "
            "(tareas=%d/%d, bytes=%d): %s",
            len(excedente), len(seleccionadas), MAX_TAREAS_POR_SESION, total_bytes,
            ", ".join(str(t["task_id"]) for t in excedente),
        )
    resultados.extend(_sin_revisar(t["task_id"], _MOTIVO_EXCEDENTE) for t in excedente)

    # Construir el contenido: por cada tarea, un rótulo + sus documentos; al final, la instrucción.
    company_ctx = _build_company_context(memory_buffer or {})
    content: list[dict] = []
    if company_ctx:
        content.append({"type": "text", "text": f"EMPRESA:\n{company_ctx}"})
    for t in seleccionadas:
        rotulo = (f"=== TAREA task_id={t['task_id']} | «{t.get('title', '')}» "
                  f"| estado declarado por el responsable: {t.get('status', '')} ===")
        if str(t.get("required_doc") or "").strip():
            rotulo += f"\nDocumento que pidió el Consejo: {str(t['required_doc']).strip()}"
        if str(t.get("description") or "").strip():
            rotulo += f"\nDescripción de la tarea: {str(t['description']).strip()}"
        content.append({"type": "text", "text": rotulo})
        content.extend(t["docs"])
    content.append({
        "type": "text",
        "text": (
            "Audita la evidencia de CADA tarea de arriba y entrega tu veredicto con la herramienta "
            "'validar_evidencias'. Un veredicto por tarea, con su task_id exacto. Recuerda: si no "
            "puedes leer un documento, es `insuficiente`; nunca inventes su contenido."
        ),
    })

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=300.0)
    try:
        response = pedir_herramienta(
            _create_with_retry,
            client,
            model=settings.DIAGNOSTICO_AI_MODEL,
            max_tokens=VALIDACION_MAX_TOKENS,
            system=VALIDACION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            tool=VALIDACION_TOOL,
            effort=settings.DIAGNOSTICO_AI_EFFORT,
        )
    except Exception:
        _log.exception("la validación de evidencias falló; las tareas quedan sin_revisar")
        return resultados + [_sin_revisar(t["task_id"]) for t in seleccionadas]

    data = _tool_input(response, VALIDACION_TOOL["name"])
    if not data:
        _log.warning("la validación de evidencias no devolvió veredictos; sin_revisar")
        return resultados + [_sin_revisar(t["task_id"]) for t in seleccionadas]

    por_id: dict[str, dict] = {}
    for v in (data.get("validaciones") or []):
        if not isinstance(v, dict):
            continue
        tid = str(v.get("task_id") or "").strip()
        if not tid:
            continue
        estado = str(v.get("estado") or "").strip().lower()
        if estado not in _ESTADOS_VALIDOS:
            estado = "insuficiente"
        veredicto = {"task_id": tid, "estado": estado, "motivo": str(v.get("motivo") or "").strip()}
        documento = str(v.get("documento") or "").strip()
        if documento:
            veredicto["documento"] = documento
        if v.get("otro_documento") is True and estado != "validada":
            veredicto["otro_documento"] = True
        cubre = str(v.get("cubre") or "").strip()
        if cubre:
            veredicto["cubre"] = cubre
        if estado != "validada":
            falta = str(v.get("falta") or "").strip()
            alternativas = v.get("alternativas") if isinstance(v.get("alternativas"), list) else []
            alternativas = [str(a).strip() for a in alternativas if str(a).strip()][:MAX_ALTERNATIVAS]
            if falta:
                veredicto["falta"] = falta
            if alternativas:
                veredicto["alternativas"] = alternativas
        por_id[tid] = veredicto

    # Toda tarea enviada debe salir con veredicto: si el Auditor omitió alguna, queda sin_revisar.
    for t in seleccionadas:
        tid = str(t["task_id"])
        resultados.append(por_id.get(tid) or _sin_revisar(tid, _MOTIVO_SIN_VEREDICTO))

    return resultados
