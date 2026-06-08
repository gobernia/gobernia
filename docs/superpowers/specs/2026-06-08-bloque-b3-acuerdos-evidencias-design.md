# Bloque B3 — Acuerdos + Evidencias (cierre gobernado) (diseño)

Fecha: 2026-06-08
Estado: aprobado para escribir plan de implementación

## Contexto

Tercer sub-proyecto del Motor de Cobertura del Consejo (Bloque B). B1 (Temas) y B2
(Orden del día) ya están en producción.

Decisión de nivel-B (acordada): **construir sobre lo que hay** — las "tareas" son
**Acuerdos**. B3 evoluciona la tarea existente (`ActionTask`) agregándole evidencia y un
cierre gobernado por evidencia. El **Tablero de Acuerdos** (vista tipo Monday) es el
sub-proyecto siguiente (B3b), no entra aquí.

Hechos del codebase relevantes:
- `ActionTask` (estados `pendiente | en_progreso | completada`) es la tarea; se edita por
  `PATCH /tasks/{id}` (`update_task` en `app/api/v1/action_plans/router.py`), autorizada por
  `_get_user_task_or_404` (vía `plan_id`→ActionPlan o `objective_id`→MonthlyPlan→AnnualPlan).
- Existe storage de archivos: `app/services/documents/storage.py` con
  `generate_storage_key(session_id, doc_id, filename)` y `async upload_to_storage(content, key)`.
  **Degrada elegante**: sin credenciales S3 devuelve la clave sin subir el archivo.
- `Document` exige `session_id` (onboarding) y trae campos de procesamiento IA → NO se reusa
  para evidencia.

## Alcance de B3

Subir **evidencia** a un acuerdo (tarea) y **gobernar el cierre por evidencia**: no se marca
"Validado" sin ≥1 evidencia. Todo visible en el drawer de la tarea (UI existente del mes).

**Fuera de alcance de B3** (capas posteriores): el Tablero de Acuerdos tipo Monday (B3b);
que los acuerdos sean *solo* creados por el sistema (hoy el usuario también agrega tareas);
descarga real de archivos (presigned URLs); snapshot de la orden del día al "celebrar" la
sesión (B-later); semáforo de cobertura (B4); PDF (B5); alertas (B6).

## Modelo de datos

### Entidad nueva: `Evidence` (tabla `evidences`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | UUID (PK) | UUIDMixin |
| `action_task_id` | UUID FK → `action_tasks.id` | `ondelete=CASCADE`, index |
| `filename` | String(255) | nombre original |
| `s3_key` | String(512) | clave en storage |
| `content_type` | String(100) | MIME |
| `size_bytes` | Integer | tamaño |
| `created_at` | timestamp | (solo created; sin updated) |

- Relación: `ActionTask.evidences: list["Evidence"]` con `cascade="all, delete-orphan"`.
- Registrar el modelo en `app/models/__init__.py`.
- **No se toca `Document`.**

## Storage

Reusa `app/services/documents/storage.py`:
- `generate_storage_key(action_task_id, evidence_id, filename)` para la clave (el primer
  argumento solo se usa como namespace de ruta; pasar el `action_task_id` es válido).
- `await upload_to_storage(content, s3_key)`.

Sin credenciales S3 el archivo no se retiene físicamente, pero el registro `Evidence` se crea
igual y el gate funciona. La retención real de archivos requiere configurar S3 (config de
infra, como Google OAuth) — se documenta, no bloquea B3.

## Endpoints

Router dedicado nuevo `app/api/v1/evidence/router.py`, montado en `main.py` con prefijo
`/api/v1` (mismo patrón que los demás routers).

| Método | Ruta | Acción |
|--------|------|--------|
| `POST` | `/tasks/{task_id}/evidence` | multipart (`file`). Valida tipo/tamaño (reusa la validación de etapa-7: PDF/Excel/Word/imagen, máx 10 MB), sube al storage, crea `Evidence`. Si la tarea está en `pendiente`, la pasa a `en_progreso`. Devuelve `EvidenceOut`. |
| `GET` | `/tasks/{task_id}/evidence` | Lista las evidencias de la tarea (metadata: id, filename, content_type, size_bytes, created_at). |
| `DELETE` | `/evidence/{evidence_id}` | Borra una evidencia. 204. |

- Autorización: la tarea debe ser del usuario (reusa/replica `_get_user_task_or_404`). Para
  `DELETE`, la evidencia se resuelve vía su `action_task_id` → tarea → usuario; 404 si no es
  suya.
- Esquemas en `app/schemas/evidence.py`: `EvidenceOut`.
- Validación de archivo: función local `_validate_file(filename, content_type, size)` en el
  router de evidencia (replica las reglas de etapa-7, **sin refactorizar etapa-7**): tipos
  permitidos PDF/Excel/Word/imagen, tamaño máx 10 MB; 400 con detalle claro si no cumple.

## Gate de cierre (el corazón de B3)

En `update_task` (`PATCH /tasks/{id}`, `app/api/v1/action_plans/router.py`): si el `body`
lleva `status` a **`completada`** y la tarea tiene **0 evidencias**, responder **409** con
detalle "Se requiere al menos una evidencia para validar este acuerdo." Si ya tiene ≥1
evidencia, permite el cambio normalmente.

- La cuenta de evidencias se hace con un `select(func.count())` sobre `evidences` por
  `action_task_id`, antes de aplicar el cambio de status.
- Solo aplica cuando el status objetivo es `completada`; otros cambios (title, owner,
  priority, due_date, o status a pendiente/en_progreso) no se bloquean.

## Estados / labels

Sin cambiar la DB: se reusan los 3 estados con relabel en el contexto de acuerdos:
`pendiente` = **Pendiente**, `en_progreso` = **En proceso**, `completada` = **Validado**.

## Frontend

En el **TaskDrawer** (`frontend/src/components/plan/TaskDrawer.tsx`), una sección
**"Evidencia"**:
- Botón para subir archivo (input file) → `POST .../evidence`; muestra la lista de evidencias
  (filename + fecha) con opción de borrar.
- El control para marcar la tarea como **Validado/completada** se deshabilita o muestra un
  aviso si la tarea no tiene evidencias; si el backend devuelve 409, se muestra el mensaje.
- `frontend/src/lib/evidence.ts` (tipos + `getEvidence(taskId)`, `uploadEvidence(taskId, file)`,
  `deleteEvidence(evidenceId)`).

## Migración / despliegue

- `scripts/create_evidences.py` (create_all; patrón de `create_board_themes.py`). Aditivo.
- Correr en Railway `python -m scripts.create_evidences` cuando el humano autorice (toca DB).
- `Document` no se modifica.

## Pruebas

Backend (pytest, db mockeada salvo donde aplique):
- `POST /tasks/{id}/evidence`: crea `Evidence`, pasa la tarea de `pendiente`→`en_progreso`,
  valida tipo/tamaño (400 en archivo inválido). (El upload al storage se mockea/degrada.)
- Gate: `PATCH /tasks/{id}` con `status=completada` y 0 evidencias → 409; con ≥1 evidencia →
  200. Otros cambios de status no se bloquean.
- `GET` lista; `DELETE` con autorización (404 si no es del usuario).
- Suite completa verde, sin regresiones.

Frontend: `tsc --noEmit` + `npm run build` verdes; lint limpio en archivos nuevos.

## Criterio de "hecho" para B3

- Tabla `evidences` creada; subir evidencia funciona (registro creado; archivo retenido si
  hay S3).
- No se puede marcar un acuerdo como Validado sin evidencia (gate 409).
- El dueño sube/ve/borra evidencia desde el drawer de la tarea.
- Suite backend verde; build frontend verde.

## Riesgos / decisiones abiertas (para sub-proyectos siguientes)

- **Tablero de Acuerdos (Monday)** → B3b.
- Descarga/preview real de evidencias (presigned URLs) → posterior; depende de S3 configurado.
- "Sufficient evidence" del brief se simplifica a "≥1 evidencia" para el gate de Validado.
