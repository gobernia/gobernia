"""
La deliberación del Consejo: los 4 consejeros dejan de ser cuatro voces y el órgano emite UNA.

Entra: los análisis revisados de los consejeros + las críticas del Abogado del Diablo + el Roadmap
(documento rector) + los KPIs del periodo.
Sale: una conclusión única, el avance contra el Roadmap, los riesgos del órgano y los ACUERDOS
(que el endpoint materializa como `Compromiso` reales, atados a un pilar del Roadmap).

NO se le vuelven a adjuntar los documentos: los análisis ya citan sus fuentes, y readjuntarlos
duplicaría el costo del board pack completo por sesión.
"""
import json
import logging
from datetime import date, timedelta

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import (
    _build_kpi_context,
    _build_roadmap_context,
    _create_with_retry,
    _filtrar_fuentes,
    _fuentes_de,
    _period_label,
    _tool_input,
    roadmap_pilares,
)
from app.schemas.board_session import normalize_analysis

_log = logging.getLogger(__name__)

DELIBERACION_MAX_TOKENS = 4096

MIN_ACUERDOS = 3
MAX_ACUERDOS = 7

_PRIORIDADES = {"alta", "media", "baja"}
_NIVELES = {"rojo", "ambar", "verde"}

# Días por defecto para un acuerdo cuya fecha sugerida no es utilizable.
_DIAS_DEFAULT = 21

SIN_ROADMAP_AVANCE = (
    "El Consejo no puede medir avance contra un Roadmap: el dueño aún no ha validado el suyo. "
    "Mientras no exista un plan rector, las recomendaciones de este Consejo se sostienen solo en "
    "los datos del periodo, no en un rumbo declarado."
)

DELIBERACION_SYSTEM_PROMPT = """Eres EL CONSEJO DE ADMINISTRACIÓN de esta empresa, hablando con UNA SOLA VOZ.

No eres un relator ni un moderador: eres el órgano. Los cuatro consejeros (CFO, CSO, CRO, Auditor)
ya deliberaron y un consejero independiente los cuestionó. Tú emites la POSTURA DEL CONSEJO.

CÓMO HABLAS:
- Le hablas AL DUEÑO, de frente. Nunca hables de la mecánica interna del Consejo: prohibido escribir
  "el CFO opina que…", "los agentes coinciden en…", "tres de cuatro consejeros…". El dueño no
  contrató cuatro asistentes: contrató un Consejo. Dices "El Consejo concluye…", "Acordamos…".
- NO es un resumen de resúmenes ni una lista de las cuatro opiniones. Es UNA conclusión.
- Donde los consejeros se CONTRADICEN, tu trabajo es RESOLVER: toma partido y di brevemente por qué
  el Consejo se inclina por una lectura y no por la otra. Un consejo que no resuelve no sirve.
- Tono ejecutivo, directo, sin relleno. Si la situación es grave, se dice.

EL ROADMAP ES EL EJE:
- El Roadmap Estratégico validado es el documento rector. `avance_roadmap` responde una sola
  pregunta: ¿cómo va la empresa CONTRA SU PLAN? Qué pilar avanza, cuál se atrasó, qué meta está en
  riesgo, y con qué evidencia.
- Si no hay Roadmap, dilo con todas sus letras y NO inventes pilares, metas ni milestones.
- Cada acuerdo debe servirle a un pilar del Roadmap. En `pilar` escribe el NOMBRE EXACTO de uno de
  los pilares que se te dieron (cópialo literal). Si el acuerdo es transversal y no le sirve a
  ninguno en particular, deja `pilar` vacío (""). NUNCA inventes un pilar que no está en la lista.

LOS ACUERDOS:
- Entre 3 y 7. Son las decisiones del órgano, no sugerencias: acciones concretas y VERIFICABLES
  (se puede decir sí o no se hizo). Nada de "mejorar la comunicación".
- `responsable_sugerido` va POR ROL ("Dirección General", "Finanzas", "Comercial"): no conoces
  nombres ni correos, y no debes inventarlos. El dueño le pondrá nombre después.
- `fecha_sugerida` en formato YYYY-MM-DD, realista y dentro del trimestre en curso.
- `racional`: por qué el Consejo lo acuerda. Una o dos oraciones.

REGLA DE CITACIÓN (INQUEBRANTABLE):
- Los riesgos que se apoyan en un documento citan su `fuente` EXACTAMENTE como la citaron los
  consejeros (mismo documento, misma página). Si un riesgo no viene de un documento, `fuente` va
  vacía ("") y se enuncia como lectura del Consejo, no como dato duro.
- NUNCA inventes cifras, documentos, páginas ni fuentes que no aparezcan en los análisis."""

DELIBERACION_TOOL = {
    "name": "conclusion_consejo",
    "description": "Entrega la conclusión única del Consejo de Administración para el periodo.",
    "input_schema": {
        "type": "object",
        "properties": {
            "conclusion": {
                "type": "string",
                "description": (
                    "La voz del Consejo dirigida al dueño: dónde está la empresa, qué decidió el "
                    "órgano y por qué. 2-5 párrafos cortos. No es un resumen de las cuatro opiniones."
                ),
            },
            "avance_roadmap": {
                "type": "string",
                "description": (
                    "Cómo va la empresa CONTRA SU ROADMAP: pilares que avanzan, los que se atrasan, "
                    "metas en riesgo, con evidencia. Si no hay Roadmap validado, dilo explícitamente."
                ),
            },
            "riesgos": {
                "type": "array",
                "description": "Los riesgos que el Consejo pone sobre la mesa, con semáforo.",
                "items": {
                    "type": "object",
                    "properties": {
                        "nivel": {
                            "type": "string",
                            "enum": ["rojo", "ambar", "verde"],
                            "description": "rojo = crítico; ambar = atención; verde = bajo control.",
                        },
                        "texto": {"type": "string"},
                        "fuente": {
                            "type": "string",
                            "description": (
                                "Documento y página, copiada literal de los análisis. "
                                "Vacía si no viene de un documento."
                            ),
                        },
                    },
                    "required": ["nivel", "texto", "fuente"],
                },
            },
            "acuerdos": {
                "type": "array",
                "description": "Los acuerdos del Consejo: entre 3 y 7, concretos y verificables.",
                "items": {
                    "type": "object",
                    "properties": {
                        "texto": {"type": "string", "description": "La acción acordada, concreta y verificable."},
                        "responsable_sugerido": {
                            "type": "string",
                            "description": "POR ROL ('Dirección General', 'Finanzas'). Nunca un nombre ni un correo.",
                        },
                        "fecha_sugerida": {
                            "type": "string",
                            "description": "Fecha límite propuesta, ISO YYYY-MM-DD, dentro del trimestre en curso.",
                        },
                        "prioridad": {"type": "string", "enum": ["alta", "media", "baja"]},
                        "pilar": {
                            "type": "string",
                            "description": (
                                "NOMBRE EXACTO de un pilar del Roadmap entregado, o \"\" si el "
                                "acuerdo es transversal. Nunca un pilar inventado."
                            ),
                        },
                        "racional": {"type": "string", "description": "Por qué el Consejo lo acuerda."},
                    },
                    "required": ["texto", "responsable_sugerido", "fecha_sugerida",
                                 "prioridad", "pilar", "racional"],
                },
            },
        },
        "required": ["conclusion", "avance_roadmap", "riesgos", "acuerdos"],
    },
}


def _fecha_default(period_year: int, period_month: int) -> str:
    return (date.today() + timedelta(days=_DIAS_DEFAULT)).isoformat()


def _norm_fecha(v, period_year: int, period_month: int) -> str:
    """ISO YYYY-MM-DD válida, o la fecha por defecto (hoy + 21d)."""
    try:
        return date.fromisoformat(str(v).strip()).isoformat()
    except (TypeError, ValueError):
        return _fecha_default(period_year, period_month)


def _norm_acuerdo(a: dict, pilares: list[str], period_year: int, period_month: int) -> dict | None:
    if not isinstance(a, dict):
        return None
    texto = str(a.get("texto") or "").strip()
    if not texto:
        return None
    prioridad = str(a.get("prioridad") or "").strip().lower()
    if prioridad not in _PRIORIDADES:
        prioridad = "media"
    # Regla dura: el pilar debe existir en el Roadmap. Un pilar inventado se vacía —
    # el acuerdo sigue vivo, pero deja de colgar de una rama que no existe.
    pilar = str(a.get("pilar") or "").strip()
    if pilar and pilar not in pilares:
        _log.warning("deliberación devolvió un pilar inexistente (%r); se vacía", pilar)
        pilar = ""
    return {
        "texto": texto,
        "responsable_sugerido": str(a.get("responsable_sugerido") or "").strip(),
        "fecha_sugerida": _norm_fecha(a.get("fecha_sugerida"), period_year, period_month),
        "prioridad": prioridad,
        "pilar": pilar,
        "racional": str(a.get("racional") or "").strip(),
    }


def _norm_riesgo(r) -> dict | None:
    if not isinstance(r, dict):
        return None
    texto = str(r.get("texto") or "").strip()
    if not texto:
        return None
    nivel = str(r.get("nivel") or "").strip().lower()
    if nivel not in _NIVELES:
        nivel = "ambar"
    return {"nivel": nivel, "texto": texto, "fuente": str(r.get("fuente") or "")}


def _fuentes_permitidas(analyses: dict) -> set[str]:
    """
    Todas las fuentes que los consejeros SÍ citaron. La deliberación no vuelve a ver los
    documentos: cualquier fuente que no salga de aquí es inventada. Si no hubo documentos,
    ningún consejero citó nada → el conjunto es vacío → se vacían todas las fuentes.
    """
    permitidas: set[str] = set()
    for a in (analyses or {}).values():
        if isinstance(a, dict):
            permitidas |= _fuentes_de(a)
    return permitidas


def _fallback(analyses: dict, roadmap: dict | None, period_year: int, period_month: int) -> dict:
    """
    Sin API key (o con el tool-use roto) el Consejo no puede deliberar, pero el dueño no
    puede quedarse sin acuerdos: se derivan de las recomendaciones que los consejeros ya dieron.
    """
    acuerdos: list[dict] = []
    fecha = _fecha_default(period_year, period_month)
    for agente, a in (analyses or {}).items():
        for rec in (normalize_analysis(a).get("recommendations") or []):
            if len(acuerdos) >= MAX_ACUERDOS:
                break
            acuerdos.append({
                "texto": rec,
                "responsable_sugerido": "Dirección General",
                "fecha_sugerida": fecha,
                "prioridad": "media",
                "pilar": "",
                "racional": f"Recomendación del análisis de {agente}, adoptada por el Consejo.",
            })

    riesgos = []
    for a in (analyses or {}).values():
        for al in normalize_analysis(a).get("alerts") or []:
            if al.get("nivel") in ("rojo", "ambar") and len(riesgos) < MAX_ACUERDOS:
                riesgos.append(al)

    tiene_roadmap = bool(roadmap_pilares(roadmap) or (roadmap or {}).get("metas_3anios"))
    return {
        "conclusion": (
            "El Consejo no pudo deliberar en esta sesión (el servicio de IA no está disponible). "
            "Abajo quedan los análisis de los consejeros y los acuerdos derivados de sus "
            "recomendaciones. Vuelve a generar el análisis para obtener la conclusión del Consejo."
        ),
        "avance_roadmap": (
            "El Consejo no pudo evaluar el avance contra el Roadmap en esta sesión."
            if tiene_roadmap else SIN_ROADMAP_AVANCE
        ),
        "riesgos": riesgos,
        "acuerdos": acuerdos,
        "_fallback": True,
    }


def run_deliberacion(
    analyses: dict,
    critiques: dict,
    roadmap: dict | None,
    memory_buffer: dict,
    kpi_snapshot: dict | None,
    period_year: int,
    period_month: int,
    documents_note: str = "",
) -> dict:
    """
    El paso que convierte cuatro opiniones en UNA conclusión del Consejo.
    Opus + tool-use forzado. Si no hay API key o el tool-use falla, cae a un fallback determinista.
    """
    if not settings.ANTHROPIC_API_KEY:
        return _fallback(analyses, roadmap, period_year, period_month)

    pilares = roadmap_pilares(roadmap)
    roadmap_ctx = _build_roadmap_context(roadmap, period_year)
    kpi_ctx = _build_kpi_context(kpi_snapshot, memory_buffer)

    if pilares:
        pilares_ctx = (
            "PILARES VÁLIDOS para el campo `pilar` de los acuerdos (cópialos LITERAL; "
            "cualquier otro valor se descarta):\n"
            + "\n".join(f"  - {p}" for p in pilares)
            + '\n  - "" (vacío) si el acuerdo es transversal.\n'
        )
    else:
        pilares_ctx = (
            "No hay pilares de Roadmap disponibles: deja `pilar` VACÍO (\"\") en TODOS los acuerdos. "
            "No inventes pilares.\n"
        )

    nota_docs = f"\nNOTA SOBRE DOCUMENTOS: {documents_note}\n" if documents_note else ""

    user_prompt = (
        f"Sesión del Consejo — periodo {_period_label(period_year, period_month)}.\n\n"
        f"{roadmap_ctx}\n\n"
        f"{kpi_ctx}\n"
        f"{nota_docs}\n"
        "ANÁLISIS DE LOS CONSEJEROS (ya revisados tras la crítica del consejero independiente). "
        "Son tu materia prima, NO tu formato de salida:\n"
        f"{json.dumps(analyses, ensure_ascii=False, indent=2)}\n\n"
        "CRÍTICAS DEL CONSEJERO INDEPENDIENTE (dónde los análisis eran débiles):\n"
        f"{json.dumps(critiques or {}, ensure_ascii=False, indent=2)}\n\n"
        f"{pilares_ctx}\n"
        "Delibera y emite la postura del Consejo con la herramienta 'conclusion_consejo'. "
        "Resuelve las contradicciones entre consejeros, no las promedies. "
        f"Entre {MIN_ACUERDOS} y {MAX_ACUERDOS} acuerdos."
    )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=300.0)
    try:
        response = _create_with_retry(
            client,
            model=settings.DIAGNOSTICO_AI_MODEL,
            max_tokens=DELIBERACION_MAX_TOKENS,
            system=DELIBERACION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[DELIBERACION_TOOL],
            tool_choice={"type": "tool", "name": DELIBERACION_TOOL["name"]},
        )
    except Exception:
        _log.exception("la deliberación del Consejo falló; se usa el fallback determinista")
        return _fallback(analyses, roadmap, period_year, period_month)

    data = _tool_input(response, DELIBERACION_TOOL["name"])
    if not data or not str(data.get("conclusion") or "").strip():
        _log.warning("la deliberación no devolvió una conclusión utilizable; fallback")
        return _fallback(analyses, roadmap, period_year, period_month)

    acuerdos = [
        x for x in (
            _norm_acuerdo(a, pilares, period_year, period_month)
            for a in (data.get("acuerdos") or [])
        ) if x
    ][:MAX_ACUERDOS]

    riesgos = [x for x in (_norm_riesgo(r) for r in (data.get("riesgos") or [])) if x]
    # Antialucinación: la deliberación no tiene los documentos a la vista. Solo puede sostener
    # las fuentes que los consejeros citaron; si no hubo documentos, no puede sostener ninguna.
    riesgos = _filtrar_fuentes(
        {"findings": [], "alerts": riesgos}, _fuentes_permitidas(analyses)
    )["alerts"]

    avance = str(data.get("avance_roadmap") or "").strip()
    if not (pilares or (roadmap or {}).get("metas_3anios")):
        avance = avance or SIN_ROADMAP_AVANCE

    return {
        "conclusion": str(data["conclusion"]).strip(),
        "avance_roadmap": avance,
        "riesgos": riesgos,
        "acuerdos": acuerdos or _fallback(analyses, roadmap, period_year, period_month)["acuerdos"],
    }
