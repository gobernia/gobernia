# Perspectivas (múltiples voces) — Diseño

**Fecha:** 2026-07-03
**Estado:** Aprobado por el usuario, listo para plan de implementación.

## Objetivo

Enriquecer el diagnóstico de Gobernia con perspectivas de **más de una persona** (no solo el
dueño/CEO): directivos, socios, empleados clave, clientes y proveedores. El valor central no es
solo "más datos", sino **detectar coincidencias, contradicciones y puntos ciegos** entre lo que
cree el dueño y lo que perciben los demás.

## Decisiones (resueltas en brainstorm)

1. **Participación:** link compartible **sin cuenta**. El invitado abre un link y responde; no se
   registra. Flujo **asíncrono** (el dueño no espera a nadie; las voces van llegando).
2. **Roles (v1):** empleado clave, directivo, socio, cliente, proveedor/aliado. Todd adapta las
   preguntas a cada rol.
3. **Preguntas:** **totalmente adaptadas al rol** (Todd pregunta solo lo que ese rol conoce bien).
   La consolidación es **temática** (por temas), no comparación pregunta-a-pregunta.
4. **Anonimato (según rol):**
   - **Empleados y clientes** → agregado/anónimo ("los empleados perciben…", "3 de 4 clientes…").
     Nunca se muestra quién dijo qué.
   - **Directivos, socios, proveedores** → atribuido (con nombre y rol).
5. **Integración:** vista **"Perspectivas"** propia + la síntesis se **inyecta como contexto extra al
   FODA y al plan**. **No** re-corre el diagnóstico web (evita costo/tiempo por cada respuesta).

## Flujo general

1. El dueño hace su onboarding y diagnóstico **como hoy** (sin cambios).
2. En `/dashboard/perspectivas` crea una **invitación** eligiendo **rol** y —para roles atribuidos—
   un **nombre**. Se genera un **token/link único**.
3. El dueño comparte el link. El invitado lo abre → **mini-entrevista con Todd por rol** (sin cuenta,
   ~5–8 preguntas, breve) → pantalla "¡Gracias!".
4. El dueño ve el estado de cada invitación (pendiente / respondió) y pulsa **"Consolidar"**.
5. Un agente Opus **sintetiza todas las voces** → coincidencias / contradicciones / puntos ciegos,
   respetando el anonimato por rol.
6. La síntesis se muestra en la vista Perspectivas y se **inyecta al contexto de FODA y plan**.

## Arquitectura

### Datos

- **Tabla nueva `perspectiva_invites`** (creada con script `create_all`, NO Alembic — ver
  [[prod_schema_no_alembic]]):
  - `id` (uuid, pk)
  - `owner_user_id` (str, index) — el dueño/empresa que invita
  - `role` (str) — uno de: `empleado`, `directivo`, `socio`, `cliente`, `proveedor`
  - `invitee_name` (str, nullable) — solo para roles atribuidos
  - `token` (str, unique, index) — para el link público
  - `status` (str, default `pending`) — `pending` | `active` | `done`
  - `messages` (JSONB) — transcript de la entrevista (mismo formato que `ToddSession`)
  - `state` (JSONB) — estado acumulado del invitado (hallazgos/percepciones por rol)
  - timestamps (created/updated)
- **Síntesis consolidada:** se guarda en `DiagnosticoEstrategico.content["perspectivas"]` (junto a
  `foda`, `metas_orden`, `factores_externos`), con forma:
  ```json
  {
    "status": "generating|active|failed",
    "generated_at": "...",
    "coincidencias": ["..."],
    "contradicciones": ["🔴 el dueño cree X, los clientes perciben Y", "..."],
    "puntos_ciegos": ["..."],
    "por_rol": { "empleado": "resumen agregado…", "cliente": "…", "directivo": "…" },
    "conteo": { "empleado": 3, "cliente": 2, ... }
  }
  ```

### Backend

- **Motor de entrevista por rol:** `app/services/ai/perspectivas/agent.py`
  - `build_perspectiva_prompt(role, empresa_ctx)` — prompt adaptativo por rol, corto (~5–8
    preguntas), **sin** el gate de cobertura de 7 áreas (es específico por rol). Reutiliza el
    `RESPONSE_TOOL` y helpers de tool-use estructurado del agente de Todd (`run_todd_turn` genérico).
  - Reutiliza `_normalize_turn`, `parse_turn`, `build_anthropic_messages` de `todd/agent.py`.
  - Bancos de preguntas por rol en `perspectivas/roles.py` (guía opcional, como `areas.AREA_BANK`).
- **Endpoints públicos (por token, SIN login):** `app/api/v1/perspectivas/public.py`
  - `GET /perspectiva/{token}` → `{role, company_name, messages, done}` (404 si token inválido).
  - `POST /perspectiva/{token}/turn` → siguiente turno (como `todd/turn`); al `done`, marca
    `status="done"`.
- **Endpoints del dueño (con login):** `app/api/v1/perspectivas/router.py`
  - `POST /perspectivas/invite` `{role, name?}` → crea invite, devuelve `{id, token, url}`.
  - `GET /perspectivas` → lista de invites con status + conteo por rol.
  - `DELETE /perspectivas/{id}` → revoca una invitación.
  - `POST /perspectivas/consolidar` → dispara el agente de síntesis (Celery, como `foda_tasks`);
    escribe `content["perspectivas"]`.
  - `GET /perspectivas/sintesis` → devuelve `content["perspectivas"]` (para la vista).
- **Agente de consolidación:** `app/services/ai/perspectivas/consolidar.py`
  - `consolidar_perspectivas(owner_memory_buffer, invites)` — Opus tool-use, sin web. Lee el estado
    del dueño (hallazgos) + los `state`/`messages` de los invitados completados → produce la síntesis.
  - **Respeta el anonimato:** para `empleado`/`cliente` agrega ("los empleados…"), nunca nombres;
    para `directivo`/`socio`/`proveedor` puede atribuir con nombre.
  - `_fallback` determinista (sin API key / error): agrega textos por rol sin análisis.
- **Integración FODA/plan:** añadir la síntesis de perspectivas al contexto que ya consumen
  (`foda.py` recibe `perspectivas` en su prompt; `foda_into_plan.augment_buffer_with_foda` inyecta
  un resumen de perspectivas al `ai_context.company_narrative`).

### Frontend

- **Dueño — `/dashboard/perspectivas`:**
  - Crear invitación: selector de rol + (si aplica) nombre → genera link → botón "Copiar link".
  - Lista de invitaciones con estado (pendiente/respondió) y rol; opción de revocar.
  - Botón "Consolidar" (con polling mientras `generating`).
  - Vista de síntesis: **Coincidencias**, **Contradicciones** (destacadas), **Puntos ciegos**,
    y resumen por rol (respetando anonimato).
  - Ítem "Perspectivas" en el Sidebar.
- **Invitado — página pública `/p/{token}`:**
  - Reutiliza el wizard de Todd (mismo estilo, con logo Gobernia), sin login.
  - Encabezado que ubica al invitado ("Te invitaron a compartir tu perspectiva sobre {empresa}").
  - Cierre "¡Gracias! Tu perspectiva ayudará a mejorar la empresa."
  - Fuera del layout autenticado del dashboard (ruta pública propia).

### Privacidad y seguridad

- El token es la credencial de acceso público a UNA invitación; sin token no hay acceso.
- Los roles anónimos (empleado/cliente) **nunca** exponen nombre ni respuesta individual en la vista
  del dueño ni en la síntesis; solo agregados por grupo de rol.
- La ruta pública `/p/{token}` no requiere cuenta y solo permite responder esa invitación.
- La entrevista del invitado se envía al proveedor de IA (Anthropic) para generar los turnos, igual
  que el resto del análisis (coherente con la sección de seguridad de la landing).

## Alcance v1 (YAGNI)

**Incluye:** invitar por link (rol + nombre opcional), entrevista adaptada por rol, consolidación con
anonimato por rol, vista Perspectivas, inyección a FODA/plan.

**Deja fuera (después):** recordatorios/notificaciones automáticas al invitado; edición de respuestas
por el invitado; analítica avanzada por proveedor; límites/cuotas de invitaciones; expiración de
tokens.

## Pruebas

- **Unit:** `build_perspectiva_prompt` por rol (incluye datos esenciales del rol, no pide lo que el
  rol no sabe); parseo de turnos; `consolidar_perspectivas` respeta anonimato (empleado/cliente sin
  nombre) y `_fallback` no truena; bancos de roles bien formados.
- **Integración:** `POST /perspectivas/invite` crea invite y token; `GET /perspectiva/{token}`
  público devuelve el rol correcto y 404 con token inválido; `POST /perspectiva/{token}/turn` avanza
  y marca `done`; `GET /perspectivas` lista con status; revocar borra; consolidar escribe
  `content["perspectivas"]`.

## Despliegue

- Tabla `perspectiva_invites` vía `backend/scripts/create_perspectiva_invites.py` (`create_all`),
  corrido en prod **solo con autorización humana**.
- Registrar la tarea Celery de consolidación en el `include` del worker.
- Push a **ambos remotos** (origin=web/Vercel, cbeuvrin=worker/Railway).
