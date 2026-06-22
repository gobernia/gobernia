# Todd — Onboarding como formulario guiado + edición — Diseño

**Fecha:** 2026-06-20
**Alcance:** Rediseñar la experiencia de Todd de **chat** a **formulario guiado paso a paso** (una pregunta por tarjeta, Todd con avatar + encuadre, controles de formulario, progreso por las 7 áreas) + **edición con "Atrás"** (corregir una respuesta; Todd decide si conservar las posteriores o repreguntar). Reutiliza el motor de Todd (Plan 1) y el flujo de diagnóstico (Plan 2) ya construidos.

## Goal

Que el onboarding **se sienta como un formulario profesional y serio** (no un chat casual), pero conservando la inteligencia adaptativa de Todd: él decide la siguiente pregunta según las respuestas. El usuario avanza paso a paso con controles de formulario, ve su progreso por área, y puede **corregir** respuestas anteriores; al editar, Todd evalúa si la corrección afecta lo que sigue y, si es así, avisa y repregunta desde ese punto.

## Architecture

**El backend se reutiliza casi entero.** El motor de Todd (`run_todd_turn`, tool use forzado, estado acumulado, cobertura de 7 áreas) ya devuelve por turno exactamente lo que un formulario dinámico necesita: `{message, options, input ("text"|"single_choice"), state, done}`. El rediseño es **mayormente frontend** (presentar cada turno como un paso de formulario en vez de burbujas de chat), más una **extensión chica de backend** para la edición.

- **Frontend:** `frontend/src/app/onboarding/todd/page.tsx` se reescribe de chat a **wizard de una pregunta por tarjeta**. La conversación/estado sigue viniendo de los endpoints existentes (`GET /onboarding/todd`, `POST /onboarding/todd/turn`, `POST /onboarding/todd/close`).
- **Backend:** `RESPONSE_TOOL` gana un campo `reanudar_desde`; nuevo endpoint `POST /onboarding/todd/edit` para corregir una respuesta con análisis de impacto por parte de Todd.

## Tech Stack

- Backend: FastAPI, SQLAlchemy async, anthropic (Sonnet 4.6, tool use). Sin migración (reusa `todd_sessions`).
- Frontend: Next.js 16 App Router, framer-motion, lucide-react, axios (`@/lib/api`). Estilo de marca (`--gob-navy`/`--gob-bone`/`--gob-ink`).

---

## Componente 1 — UI del formulario guiado (wizard)

**Reescribir:** `frontend/src/app/onboarding/todd/page.tsx`. **Ajustar:** `frontend/src/lib/todd.ts` (tipos/cliente para edición).

- **Una pregunta por tarjeta**, centrada (no chat). Transición discreta entre pasos (framer-motion).
- **Encabezado de Todd:** avatar pequeño (monograma/ícono limpio como placeholder, intercambiable por una imagen luego) + nombre "Todd" + su **línea de encuadre** = el `message` del turno actual.
- **Control de respuesta** según `input`:
  - `single_choice` → botones tipo opción (las `options`), p. ej. Sí / Más o menos / No. Al elegir, avanza.
  - `text` → campo de texto (input/textarea) + botón **"Continuar"**.
- **Barra de progreso por las 7 áreas** derivada de `state.areas_cubiertas` (las 7: estrategia, comercial, operativo, rh, financiero, legal, familiar) → "X/7" + indicador visual. (El `state` ya viene en la sesión; se expone en el GET — ver Componente 3.)
- **Botón "Atrás"** siempre visible (abre el panel de edición — Componente 2).
- Al `done` → pantalla de carga ("Todd está preparando tu diagnóstico…") → navega a `/dashboard/diagnostico` (igual que hoy; el diagnóstico ya se dispara en `close`).
- Estilo serio, consistente con la marca.

## Componente 2 — Edición con "Atrás"

**Frontend** (panel/lista en la misma página) + **backend** (endpoint de edición).

- **"Atrás"** abre una **lista de las respuestas dadas**: pares *pregunta de Todd → respuesta del usuario*, que el front arma desde los `messages` de la sesión (alternan todd/user). Cada par es clickeable.
- El usuario **hace clic en una respuesta** → la corrige con el mismo tipo de control (texto u opciones, según corresponda).
- Al confirmar la corrección, el front llama `POST /onboarding/todd/edit {answer_index, nueva_respuesta}`.
- **Backend (`edit`)**: reconstruye el transcript con la respuesta corregida en su posición, y le pasa a Todd (vía el motor) la corrección + las **respuestas posteriores** que el usuario ya había dado, pidiéndole que decida (campo `reanudar_desde`):
  - **"continuar"** → las posteriores siguen siendo válidas: se conservan y Todd continúa donde iba.
  - **"rehacer"** → la corrección las invalida: se **descartan** las posteriores, Todd **avisa** ("Con ese cambio, repasemos un par de cosas desde aquí") y **repregunta** desde el punto editado.
  - **Fallback seguro:** si Todd no decide claramente, se asume **"rehacer"** (mejor consistente que arrastrar respuestas inválidas).
- Persiste el nuevo transcript + estado en `todd_sessions` y devuelve el siguiente turno (mismo shape que `/turn`).

## Componente 3 — Backend: campo de impacto + endpoint de edición + exponer estado

**Modificar:** `backend/app/services/ai/todd/agent.py` (`RESPONSE_TOOL`, `_normalize_turn`, un `run_todd_edit`), `backend/app/api/v1/todd/router.py` (endpoint `edit` + exponer `areas_cubiertas`/`state` en el GET), `backend/app/schemas/todd.py`.

- **`RESPONSE_TOOL`** gana una propiedad opcional `reanudar_desde` (string: `"continuar"` | `"rehacer"`), y `_normalize_turn` la incluye en el turno normalizado (default `"continuar"`; en el flujo normal —no edición— se ignora).
- **`run_todd_edit(messages_corregidos, posteriores)`** (o un parámetro `edit_context` en `run_todd_turn`): arma el prompt con la corrección + las respuestas posteriores y pide a Todd la decisión `reanudar_desde` + el siguiente turno. Salida estructurada (tool use), igual que el resto.
- **Endpoint `POST /onboarding/todd/edit`** (`{answer_index: int, nueva_respuesta: str}`): valida el índice, reconstruye el transcript, llama a `run_todd_edit`, aplica continuar/rehacer, persiste, devuelve `ToddTurnOut`.
- **GET `/onboarding/todd`** se extiende para incluir lo que el wizard necesita para el progreso: las **áreas cubiertas** (de `state.areas_cubiertas`). Se agrega `areas_cubiertas: list[str]` (y opcionalmente el `state`) a `ToddSessionOut`. (El `POST /turn` también puede devolver `areas_cubiertas` para actualizar el progreso sin recargar.)

## Out of scope

- Cambiar el motor de generación de preguntas de Todd (se queda igual).
- Cambiar el diagnóstico (Plan 2 ya hecho).
- Enlazar Todd como entrada por defecto del onboarding (se decide aparte; este spec es la pantalla en sí).
- "Atrás" libre de navegación por pasos previos como wizard clásico editable in-situ — la edición es vía el panel de lista (más simple y suficiente).

## Decisiones tomadas

- **Formulario guiado**, no chat (más serio para un diagnóstico empresarial). (Usuario.)
- **Todd con avatar pequeño + encuadre** (placeholder de monograma). (Usuario.)
- **Edición:** "Atrás" → lista de respuestas → corregir → Todd decide conservar/rehacer; si afecta, **avisa y repregunta**; fallback a rehacer si hay duda. (Usuario.)
- Reutilizar backend del motor + endpoints; el rediseño es mayormente frontend.

## Testing

- **Backend (pytest, LLM mockeado):** `_normalize_turn` incluye `reanudar_desde` (default `"continuar"`); endpoint `edit` (corrige una respuesta → con `run_todd_edit` mockeado a "rehacer" trunca posteriores y repregunta; a "continuar" las conserva); GET expone `areas_cubiertas`.
- **Frontend:** `npm run lint` + `npm run build` + smoke (avanzar paso a paso, ver progreso por área, "Atrás" → editar una respuesta → continuar/rehacer, finalizar → diagnóstico).

## Notas / riesgos

- **Decisión de impacto = juicio del LLM.** El campo `reanudar_desde` puede equivocarse; por eso el **fallback es "rehacer"** (consistencia > comodidad). En la práctica, las correcciones de respuestas recientes casi siempre son "rehacer" trivial (poco que repreguntar) y las independientes "continuar".
- **Transcript en edición:** al "rehacer", se truncan los mensajes posteriores al editado; al "continuar", se conservan. La lista de edición se arma desde `messages` (pares todd/user) — robusta porque el transcript siempre alterna.
- **Avatar:** placeholder (monograma "T" o ícono). Si hay imagen de Todd, se sustituye sin tocar la lógica.
- El motor de Todd y el flujo de diagnóstico (Plan 1/2) **no se tocan** salvo el campo `reanudar_desde` aditivo.
