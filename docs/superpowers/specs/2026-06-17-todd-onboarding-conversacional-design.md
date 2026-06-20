# Todd — Onboarding conversacional con diagnóstico — Diseño

**Fecha:** 2026-06-17
**Alcance:** Primer paso de un rediseño mayor. Reemplaza el onboarding de 8 pasos (formulario) por una **entrevista conversacional** conducida por un secretario virtual llamado **Todd**, que captura todo lo que la app necesita y al cerrar produce un **diagnóstico combinado** (autoevaluación interna + investigación web). Pasos posteriores (plan, etc.) quedan fuera de este spec.

## Goal

Que el usuario haga su onboarding **platicando con Todd** (un chat estilo Claude, con preguntas de texto libre y de selección simple que se despliegan según sus respuestas) en lugar de llenar un formulario rígido. Todd tiene **libertad** para decidir qué preguntar — usando como referencia el banco de ~50 afirmaciones de evaluación y las preguntas del onboarding actual, sin estar obligado a hacerlas todas — para reunir lo suficiente y entregar un **buen diagnóstico**: fortalezas y debilidades por área (interno) + contexto de competencia/mercado/economía (web). Al terminar, la app queda con los datos que ya consume hoy (para que el plan y todo lo demás sigan funcionando).

## Architecture

Un **agente conversacional turno a turno** (híbrido libre + cobertura de áreas):

- **Frontend:** una pantalla de chat (`/onboarding` rediseñado o `/onboarding/todd`) que muestra la conversación, captura respuestas (texto u opciones), y al cerrar dispara el diagnóstico y lleva a su vista.
- **Backend:** por cada turno, el front manda la conversación al backend, que llama a **Sonnet 4.6** con el prompt de Todd (persona + banco de referencia + datos esenciales a obtener + reglas de cobertura). El modelo devuelve, en JSON estructurado: el mensaje de Todd, opciones de selección (si aplica), el **estado acumulado** (datos capturados + áreas cubiertas + fortalezas/debilidades provisionales) y un flag `done`. El estado se persiste.
- **Cierre:** cuando `done` (o el usuario finaliza), el backend (1) escribe el `memory_buffer` con la estructura que la app ya usa + las fortalezas/debilidades, marca el onboarding completo; (2) dispara la generación del **diagnóstico combinado** con **Opus 4.8 + web_search** (reutilizando el motor de `diagnostico_estrategico.py` con streaming, ya arreglado), inyectando las fortalezas/debilidades internas como insumo.

El formulario de 8 pasos **no se borra**: queda como respaldo/fallback (oculto o accesible por ruta directa) hasta que Todd esté probado.

## Tech Stack

- Backend: FastAPI, SQLAlchemy async, Celery (para el diagnóstico final, que tarda minutos), Anthropic SDK. **Sonnet 4.6** (`settings.AI_MODEL`) para los turnos del chat; **Opus 4.8** (`settings.DIAGNOSTICO_AI_MODEL`) + `web_search_20260209` (streaming, `_stream_with_retry`) para el diagnóstico final.
- Frontend: Next.js 16 App Router, framer-motion, axios vía `@/lib/api`.
- Persistencia: tabla nueva para la sesión de Todd (transcript + estado) — creada vía script `create_*`/`alter_*` (NO Alembic; ver [[prod-schema-no-alembic]]). Reusa `OnboardingSession.memory_buffer` como destino final de los datos estructurados.

---

## Componente 1 — Banco de referencia (las ~50 afirmaciones por área)

Las afirmaciones que el usuario proporcionó, agrupadas en 7 áreas. **Son una guía opcional**: Todd decide cuáles tocar según la conversación; cada una respondida se interpreta como **fortaleza** (se cumple), **debilidad** (no se cumple) o **parcial**.

- **Estrategia:** sistemas de información (ERP/MRP/CRM); confianza en los datos de sus sistemas para decidir; planeación estratégica + misión/visión; proyecciones anuales de ingreso/costo/gasto; consejo (consultivo/administración) que evalúa a la dirección; tablero de indicadores de objetivos; claridad sobre uso de utilidades e inversiones.
- **Comercial:** nicho de mercado identificado; participantes de la toma de decisión identificados; conoce/satisface los insights de los tomadores de decisión; propuesta de valor clara; venta pulverizada (no concentrada); listas de precios y descuentos claras; identidad corporativa (marca/logo) clara y reconocida; estrategias publicitarias/prospección; programa de desarrollo comercial (distribuidores/vendedores); plan de diversificar/ampliar cartera; plan de expansión geográfica corto/mediano plazo; programas para no perder clientes actuales; programas de lealtad.
- **Operativo:** certificaciones de procesos (ISO/NOMs/FDA); procesos principales mapeados; libres de cuellos de botella; inventarios óptimos y bien contabilizados; precios de compra competitivos; programa de desarrollo/evaluación de proveedores; indicadores de desempeño de procesos; distribución óptima (entregas a tiempo y completas); maquinaria/equipo/tecnología para ser eficientes; usa ≥60% de capacidad instalada.
- **RH:** proceso formal de reclutamiento/contratación; rotación baja o en promedio de industria; sueldos en/por encima de la industria; compensación ligada a desempeño; claridad de funciones y responsabilidades del personal; manuales de operación/funciones/perfiles; plan DNC (detección de necesidades de capacitación); plan de desarrollo y crecimiento interno.
- **Financiero:** revisa P&L del negocio; contabilidad en tiempo y forma ante instituciones; balance general claro y bien valuado; método de costeo directo por producto/unidad; presupuesto y control presupuestal (contralor); índice de apalancamiento < 2; sujeto de crédito / tiene créditos bancarios; reserva de capital para crecer; ganancias reales ≥ promedio de industria.
- **Legal:** al corriente fiscal y libre de requerimientos fiscales; libre de demandas/requerimientos legales; conocimiento protegido (marca registrada, fórmulas, patentes).
- **Familiar:** responsabilidades de familiares en la empresa definidas y cumplidas; libre de conflictos familiares que arriesguen la continuidad; finanzas familiares separadas de las de la empresa; proceso de sucesión claro.

Estas afirmaciones viven en una constante del backend (ej. `app/services/ai/todd/areas.py`) para inyectarlas al prompt y para estructurar las fortalezas/debilidades de salida.

## Componente 2 — Motor conversacional de Todd (turno a turno, Sonnet)

**Crear:** `app/services/ai/todd/agent.py` (lógica pura del prompt + parseo) y el endpoint que lo expone.

- **Persona:** Todd, secretario del consejo — cálido, profesional, claro; una pregunta a la vez; explica brevemente por qué pregunta cuando ayuda.
- **Entrada al modelo (cada turno):** historial de la conversación + el banco de referencia (las 7 áreas con sus afirmaciones) + la lista de **datos esenciales** que sí debe obtener para no romper la app (ver Componente 3) + reglas: cubrir las 7 áreas con libertad de saltar/inferir/profundizar; no repetir lo ya sabido; preferir preguntas concretas; ofrecer opciones de selección cuando la respuesta sea acotada.
- **Salida del modelo (JSON estricto, parseo tolerante):**
  ```
  {
    "message": "texto de Todd para el usuario",
    "options": ["..."] | null,        // selección simple cuando aplique
    "input": "text" | "single_choice",
    "state": {                          // estado acumulado (se persiste y se reinyecta)
      "company": {...}, "kpis": {...}, "vision": {...}, "governance": {...},
      "areas_cubiertas": ["estrategia", ...],
      "hallazgos": { "estrategia": [{"tipo":"fortaleza|debilidad|parcial","texto":"..."}], ... }
    },
    "done": false                       // true cuando ya tiene suficiente
  }
  ```
- **Modelo:** `settings.AI_MODEL` (Sonnet 4.6). Reintentos con `_create_with_retry`.
- **Topes/guardrails:** límite máximo de turnos (ej. 40) para evitar conversaciones infinitas; `done=true` permitido solo cuando `areas_cubiertas` cubre las 7 (o el usuario fuerza el cierre). Si el LLM intenta cerrar antes, el backend lo empuja a seguir.
- **Lógica pura testeable:** construcción del prompt a partir de (historial, estado), y `parse_turn(raw) -> {message, options, input, state, done}` con defensa ante JSON inválido.

## Componente 3 — Captura estructurada → `memory_buffer`

El `state.*` que Todd acumula mapea a la **estructura que la app ya consume** (ver `_build_company_context`, `kpi_labels_from_buffer`, generación del plan):

- `company`: `name`, `industry`, `employees`, `annual_revenue`, `years_operating`, `has_board`, `is_family_business`, `website`, `competitors[]`.
- `kpis`: dict por categoría → lista de `{label, current_value, benchmark, unit, alert}`. Todd pide unos pocos números clave de forma natural; si el usuario no los tiene, registra el KPI cualitativo (sin `current_value`) y **no bloquea**.
- `vision`: `{statement}`.
- `governance`: `{score, level}` (Todd estima un score 0–100 a partir de las respuestas de gobierno/consejo, o se deja null).
- `ai_context.company_narrative`: resumen breve que arma Todd.
- `hallazgos`: fortalezas/debilidades/parciales por área (insumo del diagnóstico).

**Al cerrar (`done`):** el backend escribe `OnboardingSession.memory_buffer` con esta estructura, setea `completed_stages = [1..8]` y `completed_at` (para que el resto de la app vea el onboarding como completo), y guarda `hallazgos` (en el memory_buffer y/o para el diagnóstico). Helper puro `state_to_memory_buffer(state) -> dict` testeable.

## Componente 4 — Diagnóstico combinado (al cerrar, Opus + web)

**Modificar:** `app/services/ai/diagnostico_estrategico.py` (aceptar las fortalezas/debilidades internas como insumo) y el flujo de cierre.

- Al cerrar, se crea/dispara un `DiagnosticoEstrategico` (status `generating`) y su task de Celery (ya existe el patrón) que llama al motor con **streaming** (Opus + web_search, ya arreglado).
- El prompt del diagnóstico recibe, además del contexto de empresa, las **fortalezas/debilidades por área** que Todd recogió, e instruye a **integrarlas con la investigación web** en un diagnóstico único.
- El `content` del diagnóstico se extiende con una sección/estructura de **fortalezas y debilidades por área** además de las 6 secciones narrativas actuales (resumen, presencia digital, competencia, tendencias, contexto económico, conclusiones).
- La vista de diagnóstico existente (revista + PDF) se amplía para mostrar las fortalezas/debilidades.

## Componente 5 — UI del chat

**Crear:** pantalla de chat de Todd (ej. `frontend/src/app/onboarding/page.tsx` rediseñada, o `/onboarding/todd`), y el cliente `frontend/src/lib/todd.ts`.

- Burbujas de conversación (Todd / usuario), entrada de texto y, cuando Todd manda `options`, **botones de selección simple**.
- Indicador discreto de avance (áreas cubiertas / total).
- Al recibir `done` (o botón "Finalizar"): pantalla de carga ("Todd está preparando tu diagnóstico…") y al terminar el diagnóstico → su vista (revista).
- Animaciones discretas (framer-motion). Estilo consistente con la marca (navy/bone/ink).

## Componente 6 — Persistencia

**Crear:** modelo `ToddSession` (tabla nueva): `user_id`, `messages` (JSONB, transcript), `state` (JSONB), `status` (`active`/`done`), timestamps. Tabla creada vía `scripts/create_todd_sessions.py` (patrón `create_*`, NO Alembic). Permite retomar la conversación tras recargar/salir. Al cerrar, vuelca a `OnboardingSession.memory_buffer` (Componente 3) y dispara el diagnóstico (Componente 4).

## Integración / migración

- **Ruteo:** los usuarios nuevos entran a Todd. El formulario de 8 pasos se conserva en el código (no se borra) como fallback accesible por ruta directa; se puede ocultar del flujo principal.
- **Compatibilidad:** como Todd escribe el mismo `memory_buffer` + `completed_stages`, el plan estratégico, el saludo del Secretario y lo demás siguen funcionando sin cambios.

## Out of scope (pasos siguientes, no en este spec)

- Generar el plan estratégico desde el diagnóstico (ya existe el flujo de plan; su disparo/ajuste post-Todd es otro paso).
- Edición posterior de los datos capturados por Todd (más allá del fallback al formulario).
- Voz / multimodal en el chat.

## Decisiones tomadas

- Todd **reemplaza** el onboarding (formulario queda como fallback, no se borra). (Usuario.)
- Híbrido **libre + cobertura de 7 áreas**. (Usuario.)
- Las ~50 son **banco opcional**; Todd decide qué preguntar. (Usuario.)
- Diagnóstico **combinado** interno + web, uno solo. (Usuario.)
- **Sonnet** en el chat, **Opus** en el diagnóstico. (Usuario.)
- KPIs: Todd pide números clave pero no bloquea si no los hay.
- Cierre: Todd decide (cubiertas las 7 áreas) o el usuario fuerza "finalizar".

## Testing

- **Backend (pytest, LLM mockeado):** `parse_turn` (JSON válido/ inválido → defensa); `state_to_memory_buffer` (mapeo correcto a company/kpis/vision/governance + hallazgos); construcción del prompt incluye banco + esenciales; guardrail de cierre (no `done` sin las 7 áreas); endpoint de turno (avanza estado, persiste); cierre escribe memory_buffer + dispara diagnóstico; el diagnóstico recibe los hallazgos internos.
- **Frontend:** `npm run lint` + `npm run build` + smoke (conversar, ver opciones, finalizar, ver carga → diagnóstico).

## Notas / riesgos

- **Costo/latencia:** una llamada Sonnet por turno; aceptable. El diagnóstico final (Opus + web) tarda minutos → async (Celery) + carga, como hoy.
- **Cobertura vs. libertad:** el guardrail de "7 áreas antes de cerrar" evita diagnósticos incompletos sin matar la libertad de Todd.
- **Mapeo a KPIs numéricos:** si el usuario no da números, los KPIs quedan cualitativos; el generador de plan usa `kpi_labels`, así que sigue funcionando (verificar que tolere KPIs sin `current_value`).
- **Esquema en prod:** la tabla `todd_sessions` se crea con script `create_*` autorizado por el humano al desplegar (NO Alembic — ver [[prod-schema-no-alembic]]).
