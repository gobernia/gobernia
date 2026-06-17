# Capa de evidencias con S3 + Secretario lector — Diseño

**Fecha:** 2026-06-16
**Alcance:** Config de S3 (usuario) + descarga/preview de evidencias (front+back) + cierre de mes **multimodal** donde el Secretario lee los PDFs/imágenes del mes y los valida contra la meta de cada tarea. Reutiliza el storage, las evidencias y el cierre de mes que ya existen.

## Goal

Que las evidencias (1) **se guarden de verdad** en S3, (2) se puedan **ver/descargar** desde la UI, y (3) el Secretario **lea el contenido** de los PDFs/imágenes subidos en el mes al cerrar la sesión y **juzgue si respaldan la meta** de cada tarea — tejiendo el veredicto en la calificación (`grade`), el resumen (`summary`) y las propuestas (`proposals`) del cierre. Hoy el Secretario solo verifica que el archivo *exista* (señal `tasks_missing_doc` de la Fase 3B); esta capa lo hace leer el archivo.

## Architecture

Tres partes:

- **A. Config S3 (sin código nuevo).** El storage (`app/services/documents/storage.py`) ya sube a S3 cuando `settings.AWS_ACCESS_KEY_ID` está definido; `boto3` ya está en `requirements.txt` y las 4 variables ya existen en `config.py` (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET_DOCUMENTS`). Falta que el usuario cree el bucket + IAM y ponga las variables en Railway (backend **web** y **worker**). Se documentan los pasos; no es parte del plan de código.
- **B. Descarga/preview de evidencias (código).** Helper de URL prefirmada en el storage + endpoint protegido + link "Ver" en la UI.
- **C. Cierre de mes multimodal (código).** El Secretario descarga de S3 las evidencias legibles del mes y las adjunta a la única llamada de revisión que ya existe.

Decisiones tomadas (usuario): leer **toda** la evidencia subida en el mes (no solo la de tareas con `required_doc`); **solo PDF e imágenes** (Excel/Word no se leen → nota "súbelo en PDF"); **una sola llamada multimodal** (Opción 1, no pre-paso por documento); validar contra la meta y poder **arrastrar/ajustar** tareas.

## Tech Stack

- Backend: FastAPI, SQLAlchemy async, `boto3` (ya instalado), Anthropic SDK. Claude lee PDF vía bloque `document` e imágenes vía bloque `image` (base64) — visión nativa, sin OCR. Modelo `settings.AI_MODEL` (Sonnet 4.6), el mismo que ya usa el cierre. **Sin migración** (no hay columnas nuevas).
- Frontend: Next.js 16 App Router, axios vía `@/lib/api`.

---

## Componente A — Config S3 (pasos del usuario, no código)

1. **Crear bucket** en S3 (ej. `gobernia-documents`), región a elección (ej. `us-east-1`), acceso **privado** (sin acceso público — se sirve por URL prefirmada).
2. **Crear usuario IAM** (acceso programático) con una policy mínima sobre ese bucket: `s3:PutObject`, `s3:GetObject` (y opcional `s3:DeleteObject`) en `arn:aws:s3:::gobernia-documents/*`.
3. **Poner las 4 variables** en Railway, en **ambos** servicios (web y worker): `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET_DOCUMENTS`.
4. **Verificar:** subir una evidencia desde la app → debe aparecer el objeto en el bucket; el link "Ver" (Componente B) debe abrirlo.

> El worker necesita las mismas variables porque el cierre de mes (Componente C) corre en Celery y descarga de S3.

## Componente B — Descarga / preview de evidencias

**Modificar:** `app/services/documents/storage.py`, `app/api/v1/evidence/router.py`, `frontend/src/components/...` (la `EvidenceSection` dentro de `TaskDrawer`) y su cliente en `frontend/src/lib/...`.

- **`storage.py`:** agregar `presigned_get_url(key: str, expires: int = 300) -> str | None`. Si no hay `settings.AWS_ACCESS_KEY_ID` → devuelve `None`. Si hay → `boto3` `generate_presigned_url("get_object", Params={Bucket, Key}, ExpiresIn=expires)`. Lazy-import de boto3 (igual que `upload_to_storage`).
- **`evidence/router.py`:** `GET /evidence/{evidence_id}/download`. Carga la evidencia, valida propiedad con `_get_user_task_or_404(ev.action_task_id, user_id, db)`, y devuelve `{"url": <presigned>}`. Si no hay S3 (`presigned_get_url` → `None`) → 404 con detalle "Almacenamiento no configurado". (Se devuelve la URL en JSON, no un redirect, para que el front la abra en pestaña nueva.)
- **Frontend:** en `EvidenceSection`, cada evidencia listada gana un botón/enlace **"Ver"** que hace `GET /evidence/{id}/download` y abre `url` en pestaña nueva. Si responde 404 → deshabilitado/aviso "almacenamiento no configurado".

## Componente C — Cierre de mes multimodal (el Secretario lee)

**Modificar:** `app/services/documents/storage.py`, `app/services/ai/month_review.py`, `app/api/v1/annual_plan/router.py` (`_run_close`).

- **`storage.py`:** agregar `download_from_storage(key: str) -> bytes | None`. Sin credenciales → `None`. Con S3 → `get_object` y devuelve el body en bytes. Captura excepción → `None` (no rompe el cierre).
- **`month_review.py`:**
  - `run_month_review(signals, month_focus, objectives, memory_buffer, period_label, incomplete_task_ids, documents=None)` — nuevo parámetro opcional `documents`: lista de dicts `{"kind": "pdf"|"image", "media_type": str, "data": <base64 str>, "label": str}`. Cuando `documents` viene no-vacío, el `content` del mensaje de usuario deja de ser un string y pasa a ser una **lista de bloques**: por cada documento un bloque `{"type":"document","source":{"type":"base64","media_type":"application/pdf","data":...}}` (PDF) o `{"type":"image","source":{"type":"base64","media_type":...,"data":...}}` (imagen), cada uno precedido de un bloque de texto con su `label`; y al final el bloque de texto con el `user_prompt` de siempre (señales + objetivos). Si `documents` es `None`/vacío → se manda el string de hoy (sin cambios de comportamiento).
  - Los formatos no legibles (Excel/Word/otros) **no** se descargan ni adjuntan; en su lugar `_run_close` agrega al `user_prompt` una línea tipo "Documentos no legibles este mes (pídele al usuario subirlos en PDF): …". El prompt instruye al Secretario a mencionarlo.
  - **`REVIEW_SYSTEM_PROMPT`:** agregar reglas: (a) los documentos adjuntos son las evidencias del mes; valida si **cada uno respalda la meta** de su tarea (el `label` dice de qué tarea es y qué pedía); (b) si un documento **no** respalda la meta, no des la tarea por lograda — propón arrastrarla (`carry_over_task`) o ajustarla; (c) refleja la lectura en `summary` y `grade`; (d) **no inventes** contenido de documentos que no se adjuntaron.
- **`_run_close`:** en el bloque donde ya se cargan `tasks` y `evidence_counts`:
  - Cargar las `Evidence` del mes (de las `task_ids`), con `content_type`/`filename`/`s3_key`/`action_task_id`/`created_at`.
  - Separar **legibles** (PDF, PNG, JPG/JPEG por extensión/`content_type`) de **no legibles**.
  - De las legibles, tomar hasta **`_MAX_REVIEW_DOCS = 8`** (las más recientes); para cada una `download_from_storage(s3_key)`; las que bajen OK → base64 → dict `documents` con un `label` "Documento «{filename}» de la tarea «{task.title}»" + (si la tarea tiene `required_doc`) " que pedía: {required_doc}". Las que fallen al bajar se omiten.
  - Construir la nota de no-legibles + de excedentes (si se truncó a 8).
  - Llamar `run_month_review(..., documents=documents)` (vía el `anyio.to_thread` que ya se usa). **Si S3 está apagado** (`download_from_storage` siempre `None`) → `documents` queda vacío → comportamiento de hoy.

## Out of scope

- Leer Excel/Word (se pide al usuario subir PDF).
- Veredicto explícito por-documento persistido/mostrado en la UI (hoy se teje en summary/proposals; evolución futura = Opción 2).
- Borrado del objeto en S3 al borrar la evidencia (hoy `DELETE /evidence/{id}` borra el registro; el objeto queda — limpieza diferida, no bloquea).
- Preview embebido (visor) en la app — se abre la URL prefirmada en pestaña nueva.

## Decisiones tomadas

- **Lee toda la evidencia del mes** (no solo `required_doc`). (Usuario.)
- **Solo PDF + imágenes**; Excel/Word → nota "súbelo en PDF". (Usuario.)
- **Una sola llamada multimodal** (Opción 1). (Usuario.)
- **Validar contra la meta + arrastrar/ajustar** tareas según el doc. (Usuario.)
- **Modelo Sonnet 4.6** (visión, costo) — el mismo del cierre actual.
- **Tope 8 documentos** por cierre (`_MAX_REVIEW_DOCS`).
- **Degradación sin S3:** todo sigue funcionando como hoy (solo presencia).

## Testing

- **Backend (pytest):**
  - `storage`: `presigned_get_url` y `download_from_storage` devuelven `None` sin credenciales (sin tocar red).
  - `run_month_review`: con `documents` no-vacío arma el `content` como lista de bloques (document/image + texto) — verificar la forma de los bloques con el cliente Anthropic mockeado; con `documents` vacío manda el string de hoy.
  - Helper puro de `_run_close` para seleccionar evidencias legibles + topar a 8 + armar la nota de no-legibles (extraer la lógica a una función pura testeable, ej. `select_review_documents(evidences, tasks, max_docs)` → `(legibles[], nota_no_legibles)`).
  - Endpoint `GET /evidence/{id}/download`: 404 por propiedad ajena; 404 sin S3; `{url}` con S3 mockeado.
- **Frontend:** `npm run lint` + `npm run build` + smoke (subir evidencia → "Ver" abre el archivo; con S3 configurado).

## Notas / riesgos

- **El worker necesita las variables AWS** (el cierre corre en Celery). Documentado en Componente A.
- **Costo:** una llamada multimodal con hasta 8 PDFs/imágenes a Sonnet puede ser pesada en tokens; el tope de 8 + el cap de 10 MB por archivo lo acota. Si en la práctica resulta caro, bajar `_MAX_REVIEW_DOCS`.
- **boto3 es síncrono** dentro de funciones async; `download_from_storage`/`presigned_get_url` se llaman desde contexto donde está bien (el cierre ya corre `run_month_review` en thread; el endpoint de descarga hace una sola llamada rápida). Si molesta, envolver en `anyio.to_thread` — no se hace ahora (YAGNI).
- **PDF nativo en Claude:** el modelo Sonnet 4.6 acepta el bloque `document` (PDF base64) y `image`. Verificar al implementar la forma exacta del bloque contra la doc del SDK (skill `claude-api`).
- **Páginas/tamaño de PDF:** límite del API (~32 MB / 100 páginas por PDF); nuestros archivos ya están topados a 10 MB al subir, así que cae dentro.
