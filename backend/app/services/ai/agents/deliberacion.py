"""
La deliberación del Consejo: los 4 consejeros dejan de ser cuatro voces y el órgano emite UNA.

Entra: los análisis revisados de los consejeros + las críticas del Abogado del Diablo + el Roadmap
(documento rector) + los KPIs del periodo.
Sale: una conclusión única, el avance contra el Roadmap, los riesgos del órgano y los ACUERDOS
(que el endpoint materializa como `Compromiso` reales, atados a un pilar del Roadmap).

NO se le vuelven a adjuntar los documentos: los análisis ya citan sus fuentes, y readjuntarlos
duplicaría el costo del board pack completo por sesión.

Dos momentos, un solo órgano:
- `run_deliberacion`          → la sesión mensual, CONTRA el Roadmap (ya existe un plan).
- `run_deliberacion_fundacional` → la primera sesión, ANTES de que exista el Roadmap: de su
  conclusión, sus prioridades y su tesis estratégica NACE el Roadmap.
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

# Bloque que se AÑADE al system prompt solo cuando la sesión trae datos de ejecución
# (avance de las tareas del plan y/o los acuerdos abiertos de sesiones anteriores).
DELIBERACION_SEGUIMIENTO_SYSTEM = """

EVALÚA EL CUMPLIMIENTO (esta sesión trae datos de ejecución, no solo documentos):
- Se te da el AVANCE DEL PLAN: cuántas tareas se completaron, cuáles siguen en proceso y cuáles no se
  ejecutaron, más las que se arrastran de meses anteriores. Tu trabajo es EVALUAR ese cumplimiento:
  qué se logró, qué se atrasó y por qué. El `avance_roadmap` debe reflejar ESE avance real, con esos
  datos, no una impresión general. Si algo no se ejecutó, se dice sin adornos.
- Se te dan los ACUERDOS PENDIENTES DE SESIONES ANTERIORES. Revísalos uno por uno y decide, como
  órgano, si el Consejo los MANTIENE, los REPROGRAMA o los CIERRA — y refléjalo en la conclusión y en
  los nuevos acuerdos (un acuerdo que sigue vivo se reafirma; uno cumplido se reconoce y no se repite).
- NO inventes progreso que no esté en los datos. El cumplimiento se juzga con lo que hay, no con lo
  que se esperaría."""

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


# ── La deliberación FUNDACIONAL ───────────────────────────────────────────────
# El momento en que todavía NO existe Roadmap: el Consejo se sienta por primera vez sobre el
# diagnóstico y el FODA, emite UNA postura, y de esa postura NACE el Roadmap. Por eso aquí no
# hay `avance_roadmap` (no hay plan contra el cual medir) ni `acuerdos` (todavía no hay pilares
# de los que colgarlos): hay CONCLUSIÓN, PRIORIDADES, RIESGOS y TESIS ESTRATÉGICA.

MIN_PRIORIDADES = 3
MAX_PRIORIDADES = 5
MAX_RIESGOS = 7

DELIBERACION_FUNDACIONAL_SYSTEM_PROMPT = """Eres EL CONSEJO DE ADMINISTRACIÓN de esta empresa familiar, hablando con UNA SOLA VOZ.

Es tu PRIMERA sesión. La empresa acaba de terminar su diagnóstico y su FODA. Todavía NO existe un
plan: de lo que tú concluyas aquí va a nacer el Roadmap Estratégico a 3 años, el documento rector
que va a ordenar los próximos tres años del negocio. Lo que digas aquí es el cimiento; si te
equivocas de diagnóstico, todo el plan se construye torcido.

CÓMO HABLAS:
- Le hablas AL DUEÑO, de frente. Nunca hables de la mecánica interna del Consejo: prohibido escribir
  "el CFO opina que…", "los agentes coinciden en…", "tres de cuatro consejeros…". El dueño no
  contrató cuatro asistentes: contrató un Consejo. Dices "El Consejo concluye…".
- NO resumas a los cuatro consejeros: DELIBERA. Esto no es un resumen de resúmenes ni una lista de
  cuatro opiniones. Es UNA postura.
- Donde los consejeros se CONTRADICEN, tu trabajo es RESOLVER: toma partido y di brevemente por qué
  el Consejo se inclina por una lectura y no por la otra. Un consejo que no resuelve no sirve.
- Sin jerga de consultor, sin relleno. Tono ejecutivo y directo. Si la situación es grave, se dice.

QUÉ ENTREGAS:
- `conclusion`: dónde está parada la empresa HOY y qué le exige el momento. Es lo primero que el
  dueño va a leer sobre su propia empresa.
- `prioridades`: 3 a 5, EN ORDEN de importancia. Es lo que el Consejo dice que hay que atacar. De
  aquí van a salir los pilares del Roadmap: si una prioridad no da para sostener un frente de
  trabajo de tres años, no es una prioridad, es una tarea — déjala fuera.
- `riesgos`: lo que puede descarrilar a la empresa, con semáforo (rojo = crítico, ambar = atención,
  verde = bajo control).
- `tesis_estrategica`: LA APUESTA. Hacia dónde debe ir esta empresa en los próximos tres años y POR
  QUÉ. Una idea con filo, no un deseo. Es la frase que el Roadmap va a tener que defender.

REGLA INQUEBRANTABLE:
- NUNCA inventes cifras, documentos, páginas ni hechos que no estén en la información dada. Si un
  dato no está, el Consejo razona sin él y lo dice; no lo fabrica.
- NUNCA fijes números meta (ventas objetivo, márgenes objetivo): esos los fija el dueño, no tú."""

DELIBERACION_FUNDACIONAL_TOOL = {
    "name": "postura_fundacional_consejo",
    "description": (
        "Entrega la postura única del Consejo sobre el estado de la empresa y la apuesta "
        "estratégica de la que nacerá el Roadmap a 3 años."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "conclusion": {
                "type": "string",
                "description": (
                    "La voz del Consejo dirigida al dueño: dónde está la empresa y qué exige el "
                    "momento. 2-5 párrafos cortos. No es un resumen de las cuatro opiniones."
                ),
            },
            "prioridades": {
                "type": "array",
                "description": (
                    f"{MIN_PRIORIDADES} a {MAX_PRIORIDADES} prioridades EN ORDEN de importancia: "
                    "lo que el Consejo considera que hay que atacar. De aquí nacen los pilares."
                ),
                "items": {"type": "string"},
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
                    },
                    "required": ["nivel", "texto"],
                },
            },
            "tesis_estrategica": {
                "type": "string",
                "description": (
                    "La apuesta del Consejo: hacia dónde debe ir la empresa en 3 años y por qué. "
                    "Una idea con filo, no un deseo."
                ),
            },
        },
        "required": ["conclusion", "prioridades", "riesgos", "tesis_estrategica"],
    },
}


def _norm_riesgo_simple(r) -> dict | None:
    """Riesgo del Consejo fundacional: {nivel, texto}. Sin `fuente`: la deliberación fundacional
    no tiene los documentos a la vista, así que no se le da superficie para citar nada."""
    if not isinstance(r, dict):
        return None
    texto = str(r.get("texto") or "").strip()
    if not texto:
        return None
    nivel = str(r.get("nivel") or "").strip().lower()
    if nivel not in _NIVELES:
        nivel = "ambar"
    return {"nivel": nivel, "texto": texto}


def _fallback_fundacional(analyses: dict) -> dict:
    """
    Sin API key (o con el tool-use roto) el Consejo no puede deliberar. `conclusion` sale VACÍA
    A PROPÓSITO: es la señal para que el llamador caiga al diagnóstico de siempre
    (`synthesize_diagnostico`) y la generación del plan —que tarda minutos y cuesta dinero— NO se
    pierda por esto. Las prioridades y los riesgos se derivan de lo que los consejeros ya dijeron.
    """
    prioridades: list[str] = []
    riesgos: list[dict] = []
    for a in (analyses or {}).values():
        norm = normalize_analysis(a)
        for rec in (norm.get("recommendations") or []):
            rec = str(rec).strip()
            if rec and rec not in prioridades and len(prioridades) < MAX_PRIORIDADES:
                prioridades.append(rec)
        for al in (norm.get("alerts") or []):
            r = _norm_riesgo_simple(al)
            if r and r["nivel"] in ("rojo", "ambar") and len(riesgos) < MAX_RIESGOS:
                riesgos.append(r)
    return {
        "conclusion": "",
        "prioridades": prioridades,
        "riesgos": riesgos,
        "tesis_estrategica": "",
        "_fallback": True,
    }


def run_deliberacion_fundacional(
    analyses: dict,
    critiques: dict,
    memory_buffer: dict,
    diagnostico_content: dict,
) -> dict:
    """
    La primera sesión del Consejo: los cuatro análisis + la crítica del Abogado del Diablo se
    convierten en UNA postura del órgano, y de esa postura nace el Roadmap.

    Opus + tool-use forzado. Si no hay API key o el tool-use falla, cae a un fallback determinista
    con `conclusion` vacía (el llamador debe caer a `synthesize_diagnostico`).
    """
    if not settings.ANTHROPIC_API_KEY:
        return _fallback_fundacional(analyses)

    mb = memory_buffer or {}
    dcont = diagnostico_content or {}
    vision = mb.get("vision") or {}

    user_prompt = (
        "PRIMERA SESIÓN DEL CONSEJO. Todavía no existe Roadmap: de tu postura va a nacer.\n\n"
        f"EMPRESA: {json.dumps(mb.get('company') or {}, ensure_ascii=False)[:1500]}\n"
        f"VISIÓN DEL DUEÑO: {vision.get('statement') or '(n/d)'}\n"
        f"QUÉ HARÍA QUE ESTE CONSEJO VALGA LA PENA (definición de éxito del dueño): "
        f"{vision.get('exito_consejo') or '(n/d)'}\n"
        f"KPIs: {json.dumps(mb.get('kpis') or {}, ensure_ascii=False)[:1500]}\n\n"
        f"FODA: {json.dumps(dcont.get('foda') or {}, ensure_ascii=False)[:2000]}\n"
        f"FORTALEZAS Y DEBILIDADES: "
        f"{json.dumps(dcont.get('fortalezas_debilidades') or {}, ensure_ascii=False)[:2000]}\n"
        f"RIESGOS DEL DIAGNÓSTICO: {json.dumps(dcont.get('riesgos') or [], ensure_ascii=False)[:1200]}\n"
        f"FACTORES EXTERNOS: "
        f"{json.dumps(dcont.get('factores_externos') or {}, ensure_ascii=False)[:1500]}\n"
        f"METAS PRIORIZADAS POR EL DUEÑO: "
        f"{json.dumps(dcont.get('metas_orden') or [], ensure_ascii=False)[:800]}\n\n"
        "ANÁLISIS DE LOS CONSEJEROS (ya revisados tras la crítica del consejero independiente). "
        "Son tu materia prima, NO tu formato de salida:\n"
        f"{json.dumps(analyses or {}, ensure_ascii=False, indent=2)}\n\n"
        "CRÍTICAS DEL CONSEJERO INDEPENDIENTE (dónde los análisis eran débiles):\n"
        f"{json.dumps(critiques or {}, ensure_ascii=False, indent=2)}\n\n"
        "Delibera y emite la postura del Consejo con la herramienta "
        f"'{DELIBERACION_FUNDACIONAL_TOOL['name']}'. Resuelve las contradicciones entre "
        f"consejeros, no las promedies. Entre {MIN_PRIORIDADES} y {MAX_PRIORIDADES} prioridades, "
        "en orden."
    )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=300.0)
    try:
        response = _create_with_retry(
            client,
            model=settings.DIAGNOSTICO_AI_MODEL,
            max_tokens=DELIBERACION_MAX_TOKENS,
            system=DELIBERACION_FUNDACIONAL_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[DELIBERACION_FUNDACIONAL_TOOL],
            tool_choice={"type": "tool", "name": DELIBERACION_FUNDACIONAL_TOOL["name"]},
        )
    except Exception:
        _log.exception("la deliberación fundacional falló; se usa el fallback determinista")
        return _fallback_fundacional(analyses)

    data = _tool_input(response, DELIBERACION_FUNDACIONAL_TOOL["name"])
    if not data or not str(data.get("conclusion") or "").strip():
        _log.warning("la deliberación fundacional no devolvió conclusión utilizable; fallback")
        return _fallback_fundacional(analyses)

    prioridades = [
        p for p in (str(x).strip() for x in (data.get("prioridades") or []) if x)
        if p
    ][:MAX_PRIORIDADES]
    riesgos = [
        x for x in (_norm_riesgo_simple(r) for r in (data.get("riesgos") or [])) if x
    ][:MAX_RIESGOS]

    return {
        "conclusion": str(data["conclusion"]).strip(),
        "prioridades": prioridades or _fallback_fundacional(analyses)["prioridades"],
        "riesgos": riesgos,
        "tesis_estrategica": str(data.get("tesis_estrategica") or "").strip(),
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
    avance_tareas: str | None = None,
    acuerdos_previos: str | None = None,
) -> dict:
    """
    El paso que convierte cuatro opiniones en UNA conclusión del Consejo.
    Opus + tool-use forzado. Si no hay API key o el tool-use falla, cae a un fallback determinista.

    `avance_tareas`: bloque de texto con el AVANCE del plan (tareas hechas / en proceso / sin
      ejecutar, y el detalle del periodo + las arrastradas). Si viene, el Consejo evalúa el
      cumplimiento real, no solo los documentos.
    `acuerdos_previos`: bloque de texto con los acuerdos ABIERTOS de sesiones anteriores. Si viene,
      el Consejo revisa su cumplimiento y decide si los mantiene, reprograma o cierra.
    Ambos son opcionales: sin ellos, la deliberación funciona como antes (retrocompat).
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

    # Bloques de ejecución (opcionales): cómo va el plan y qué acuerdos siguen abiertos.
    avance_ctx = (
        f"AVANCE DEL PLAN (cómo va la ejecución de las tareas; evalúa el cumplimiento con "
        f"ESTOS datos, no inventes progreso):\n{avance_tareas.strip()}\n\n"
        if avance_tareas and avance_tareas.strip() else ""
    )
    acuerdos_ctx = (
        f"ACUERDOS PENDIENTES DE SESIONES ANTERIORES (revísalos: manténlos, reprográmalos o "
        f"ciérralos, y refléjalo en la conclusión y en los nuevos acuerdos):\n"
        f"{acuerdos_previos.strip()}\n\n"
        if acuerdos_previos and acuerdos_previos.strip() else ""
    )
    # El bloque de seguimiento se añade al system prompt solo si hay datos de ejecución.
    system_prompt = DELIBERACION_SYSTEM_PROMPT + (
        DELIBERACION_SEGUIMIENTO_SYSTEM if (avance_ctx or acuerdos_ctx) else ""
    )

    user_prompt = (
        f"Sesión del Consejo — periodo {_period_label(period_year, period_month)}.\n\n"
        f"{roadmap_ctx}\n\n"
        f"{kpi_ctx}\n"
        f"{nota_docs}\n"
        f"{avance_ctx}"
        f"{acuerdos_ctx}"
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
            system=system_prompt,
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
