# Todd — Fase FODA (factores externos + priorización + matriz) — Diseño

**Fecha:** 2026-06-20
**Alcance:** Segunda etapa de Todd, **después del diagnóstico**: una **ronda externa** de preguntas (PESTEL) informada por el diagnóstico + una **priorización de metas adaptativa** (que Todd arma a la medida) → una **matriz FODA** (Fortalezas/Oportunidades/Debilidades/Amenazas) en su propia vista. Reutiliza el motor de Todd, el diagnóstico (con sus `hallazgos` internos + investigación web) y el patrón del formulario guiado ya construidos.

## Goal

Completar el análisis estratégico: lo **interno** ya lo tenemos (entrevista de Todd → fortalezas/debilidades por 7 áreas) y el **diagnóstico** ya investiga el contexto externo en web. Esta fase agrega la **percepción del dueño sobre los factores externos** (banco PESTEL), su **priorización de metas** (personalizada por Todd), y con todo eso genera una **matriz FODA** accionable. Es la base para el paso siguiente (que se diseñará aparte).

## Architecture

Flujo en **2 etapas** (decisión del usuario):

1. Entrevista interna (7 áreas) → **diagnóstico** (ya existe: Opus + web, con `hallazgos` internos).
2. **NUEVO:** sobre el diagnóstico → **ronda externa PESTEL** (wizard adaptativo de Todd) → **priorización de metas** (ranking arrastrable de una lista que Todd personaliza) → **generación FODA** (síntesis Opus) → **vista FODA** (2×2 + metas).

- **Reutiliza el motor de Todd** (`run_todd_turn`, tool use, estado, wizard) para la ronda externa, con un **banco PESTEL** en vez del banco interno de 7 áreas, y el diagnóstico inyectado como contexto.
- **Sin nueva investigación web** en el FODA: sintetiza lo ya reunido (diagnóstico + interno + externo + metas) en una llamada de Opus.
- **Sin migración**: la ronda externa vive como una "fase" de `todd_sessions`; los factores externos, el ranking y la FODA se guardan en el `content` JSONB del `DiagnosticoEstrategico` existente.

## Tech Stack

- Backend: FastAPI, SQLAlchemy async, Celery, anthropic (Sonnet 4.6 para la ronda externa; Opus 4.8 para el FODA, sin web_search). Sin migración.
- Frontend: Next.js 16 App Router, framer-motion, lucide-react, dnd para el ranking (o reordenamiento nativo simple), axios.

---

## Componente 1 — Banco PESTEL + base de metas

**Crear:** `backend/app/services/ai/todd/externo.py` con el banco de factores externos y las metas base.

Factores externos (guía opcional, Todd decide cuáles explorar), por categoría PESTEL:
- **Políticos:** cambios políticos (elecciones/reestructuras); cambios en sindicatos; afectación por eventos en otros países; burocracia/corrupción en gestión pública; apoyo al emprendimiento por programas sociales.
- **Económicos:** nuevos impuestos/aranceles; recesión global o federal; devaluación/tipo de cambio; transacciones con recursos de dudosa procedencia; cambios contables ante dependencias de gobierno; disputas comerciales que afecten oferta/demanda; líneas de crédito que promuevan crecimiento; pocas/nulas barreras de entrada para nuevos competidores.
- **Sociales:** cambio en hábitos de consumo; nuevas formas de comunicación; estándares que garanticen fiabilidad de productos/servicios; restricciones en publicidad; inseguridad en traslados de mercancías; "pirateo" de talento por competidores; modas/percepción/tendencias en el consumo.
- **Tecnológicos:** innovación en máquinas/herramientas; nuevos materiales/insumos; actualización de software; obsolescencia por avances rápidos; ventas/adquisición online; ciberdelincuencia; modelos de adquisición de tecnología (leasing) y proveeduría.
- **Ambiental:** protestas ambientalistas; normas ambientales más estrictas (local/federal); costos de recursos naturales por escasez; pandemias/enfermedades; desastres por cambio climático.
- **Legal:** permisos de operación; combate a la informalidad; plagio de marca/secretos/invenciones; corrupción en permisos; demandas por incumplimiento de contratos (servicios/proveedores/empleados); cambios en leyes laborales.

Cada categoría admite "otro (mencionar)".

Metas base (7) — Todd las **personaliza** según interno+externo (reformula/prioriza/añade):
1. Conseguir más y mejores clientes.
2. Empleados más comprometidos con los objetivos de la empresa.
3. Mayor control de calidad en los procesos.
4. Claridad de procesos, funciones, responsabilidades y objetivos.
5. Delegar la dirección, formar un consejo, diversificarse/retirarse.
6. Conocer qué tan bien va respecto al potencial de mercado.
7. Reducir costos y maximizar ganancias/flujos.

## Componente 2 — Ronda externa (Todd, fase 2)

**Modificar:** `backend/app/services/ai/todd/agent.py` (prompt/banco parametrizable por fase), `backend/app/models/todd_session.py` (campo `phase`), `backend/app/api/v1/todd/router.py` (endpoints de la ronda externa). **Frontend:** la pantalla de Todd reutiliza el wizard.

- La sesión de Todd gana una **fase**: `"interno"` (la actual) y `"externo"`. La ronda externa arranca cuando el usuario, tras ver el diagnóstico, pulsa **"Continuar al análisis del entorno"**.
- El motor (`run_todd_turn`) se parametriza por fase: en `"externo"` usa el **banco PESTEL** + el **diagnóstico** (resumen + hallazgos + secciones web) inyectado como contexto, e instruye a Todd a explorar adaptativamente los factores externos que apliquen y clasificarlos como **oportunidad** o **amenaza** (en `state.factores_externos` = `{categoria: [{tipo: "oportunidad"|"amenaza", texto}]}`).
- Mismo wizard (una pregunta por tarjeta, avatar, "Procesando…", edición con "Atrás"), con **progreso por las 6 categorías PESTEL**.
- Endpoints análogos a los internos, parametrizados por fase (o `/onboarding/todd/externo/{turn,edit}`), persistiendo en la misma `todd_session` (campos de la fase externa).

## Componente 3 — Priorización de metas (adaptativa + ranking)

**Backend:** Todd genera la **lista de metas personalizada** (a partir de las 7 base, ajustadas por interno+externo) en un turno/endpoint dedicado. **Frontend:** pantalla de **ranking arrastrable** (ordenar 1→7).

- Cuando la ronda externa termina, Todd produce una **lista de metas a priorizar** (3–8 ítems, normalmente ~7), adaptada a la empresa. Endpoint `GET /onboarding/todd/metas` → `{metas: [str]}` (Todd las arma con Sonnet, basándose en el estado interno + externo + diagnóstico).
- El frontend muestra esas metas en una **lista reordenable** (arrastrar; en móvil, botones subir/bajar). El usuario las ordena del 1 (más importante) al N.
- `POST /onboarding/todd/metas` `{orden: [str]}` guarda el ranking (en el diagnóstico o memory_buffer).

## Componente 4 — Generación de la matriz FODA (Opus, síntesis)

**Crear:** `backend/app/services/ai/foda.py` (`generate_foda(memory_buffer, diagnostico_content, factores_externos, metas_orden) -> dict`). **Disparo:** al cerrar la priorización.

- Una llamada a **Opus 4.8 (sin web_search)** que recibe: fortalezas/debilidades internas (`hallazgos`), las secciones del diagnóstico (web), los factores externos (PESTEL), y el ranking de metas; y produce la **matriz FODA** estructurada:
  ```
  {"fortalezas": [str], "oportunidades": [str], "debilidades": [str], "amenazas": [str],
   "sintesis": "string", "metas_priorizadas": [str]}
  ```
  (Fortalezas/Debilidades = interno; Oportunidades/Amenazas = externo; `sintesis` = lectura cruzada breve; `metas_priorizadas` = el orden confirmado.)
- Salida estructurada (tool use forzado, como Todd) para garantizar JSON. Parser tolerante + fallback (arma la FODA mínima a partir de los `hallazgos` + factores si el LLM falla).
- Se guarda en `DiagnosticoEstrategico.content["foda"]` (+ `factores_externos`, `metas_orden`). Corre async (Celery) como el diagnóstico, con estado/poll, o síncrono si es rápido (sin web es de segundos-1min) — se decide en el plan; default async para consistencia.

## Componente 5 — Vista FODA (propia, 2×2)

**Crear:** `frontend/src/app/dashboard/foda/page.tsx` + `frontend/src/lib/foda.ts`. Ítem en el sidebar.

- **Matriz 2×2** clásica: Fortalezas · Oportunidades / Debilidades · Amenazas, cada cuadrante con sus puntos (color por tipo). Encabezado con la `sintesis`.
- Debajo, las **metas priorizadas** 1→N.
- Estados de carga (mientras genera) + regenerar. (PDF, futuro.)

## Out of scope

- El paso siguiente al FODA (se diseñará aparte; el usuario dijo "luego sigue otro paso").
- Nueva investigación web en el FODA (sintetiza lo ya reunido).
- Enlazar Todd como entrada por defecto (pendiente separado).

## Decisiones tomadas

- **2 etapas**: diagnóstico en medio; la ronda externa se informa del diagnóstico. (Usuario.)
- **Priorización por ranking arrastrable**, con **metas que Todd personaliza** según interno+externo. (Usuario.)
- **FODA en vista propia** (matriz 2×2 + metas). (Usuario.)
- **FODA sin nueva búsqueda web** (síntesis Opus). (Decisión, confirmada.)
- Reutiliza el motor de Todd (ronda externa = fase 2) y guarda todo en el `content` del diagnóstico (sin migración).

## Testing

- **Backend (pytest, LLM mockeado):** banco PESTEL/metas presentes; `run_todd_turn` en fase externa arma prompt con PESTEL + diagnóstico; clasificación de factores a oportunidad/amenaza; `generate_foda` ensambla la matriz desde hallazgos+factores+metas (con fallback); endpoints de ronda externa, metas y FODA.
- **Frontend:** lint + build + smoke (ronda externa en el wizard, ranking arrastrable, ver matriz FODA).

## Notas / riesgos

- **Costo/tiempo:** la ronda externa = llamadas Sonnet por turno (baratas); el FODA = 1 llamada Opus sin web (rápida). Mucho más liviano que el diagnóstico.
- **Reutilización del wizard:** la fase externa usa el mismo componente; se parametriza por fase para no duplicar UI.
- **Persistencia:** todo (factores externos, metas, FODA) en `DiagnosticoEstrategico.content` (JSONB) → sin migración; retrocompatible (diagnósticos viejos sin estas claves siguen válidos).
- **Edición:** la ronda externa hereda la edición con "Atrás" del wizard. El ranking se puede reordenar libremente antes de confirmar.
