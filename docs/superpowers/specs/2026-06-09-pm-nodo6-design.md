# Nodo 6 — Seguimiento PM (V1 sin correo automático) — diseño

Fecha: 2026-06-09
Estado: aprobado para escribir plan de implementación

## Contexto

Implementa el **nodo 6** del doc "Pipeline Consejo + PM": el sistema de seguimiento que convierte
las decisiones cerradas en **compromisos rastreables** y opera como project manager. El doc pide
nudges por correo (+7/+14/+21) y una página sin login para que el responsable reporte avance.

Decisiones de brainstorming (2026-06-09):
1. **Correo diferido:** no hay infra de correo (ni SendGrid/Resend/SMTP) ni scheduler en el repo.
   V1 construye el modelo rastreable + la página sin login + el tablero del dueño con el **estado
   de nudge computado por fecha** y un botón **"copiar link"**. El envío automático de correos y el
   scheduler quedan para después (requieren proveedor externo).
2. **Creación:** al cerrar A/B en `POST /annual-plan/minuta/decision` se crea un `Compromiso`.
3. **Evidencia = link** (no archivo) en V1.

Reusa: el patrón de modelo (`Base, UUIDMixin, TimestampMixin`; `UUIDMixin.id` tiene
`default=uuid.uuid4`), creación de tabla vía `Base.metadata.create_all` (script idempotente como
`scripts/create_board_themes.py`), registro de modelos en `app/models/__init__.py`, y el patrón de
endpoints/test del router de annual_plan. Los compromisos hoy viven dentro de la Minuta (JSONB);
este nodo los **promueve a una tabla real** (la minuta es un snapshot; el `Compromiso` es la entidad
durable rastreable).

## Alcance V1

Modelo `Compromiso`, creación al cerrar decisiones, endpoints del dueño + públicos (token), página
sin login, y tablero del dueño con estado de nudge.

**Fuera de V1:** envío automático de correos (+7/+14/+21) + scheduler; subida real de archivos
(evidencia = link); que el compromiso vencido reentre como TemaCandidato a la agenda (nodo 4);
multi-rol completo (Equipo Ejecutivo, V2 del doc).

## Backend

### Modelo `app/models/compromiso.py`
```python
class Compromiso(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "compromisos"
    user_id: Mapped[str]                  # dueño; String, index
    descripcion: Mapped[str]              # Text
    responsable_email: Mapped[str | None] # String, nullable
    responsable_nombre: Mapped[str | None]# String, nullable
    fecha_compromiso: Mapped[date | None] # Date, nullable
    status: Mapped[str]                   # "abierto"|"en_progreso"|"completado"; default "abierto"
    token: Mapped[str]                    # String, unique, index (secrets.token_urlsafe)
    avances: Mapped[list | None]          # JSONB, default list: [{fecha, pct, nota, evidencia_url}]
    source: Mapped[dict | None]           # JSONB: {month_id, tema_id} (de la minuta)
```
- Registrar en `app/models/__init__.py` (import + `__all__`).
- Script `backend/scripts/create_compromisos.py` (patrón `create_board_themes.py`: importa
  `app.models`, `Base.metadata.create_all`).

### Función pura `app/services/governance/pm.py`
```
def nudge_estado(status: str, ref_date: date, fecha_compromiso: date | None, today: date) -> str
```
- `ref_date` = fecha del último avance, o la fecha de creación si no hay avances (la calcula el caller).
- Reglas: `status == "completado"` → `"completado"`; `fecha_compromiso < today` (y no completado)
  → `"vencido"`; si no, por `dias = (today - ref_date).days`: `>=21` → `"sin_avance_rojo"`,
  `>=14` → `"sin_avance_amarillo"`, `>=7` → `"recordatorio"`, else `"al_dia"`.

### Esquemas `app/schemas/pm.py`
```python
class AvanceItem(BaseModel):
    fecha: str
    pct: int
    nota: str | None = None
    evidencia_url: str | None = None

class CompromisoOut(BaseModel):       # vista del dueño (incluye token para el link)
    id: str
    descripcion: str
    responsable_email: str | None
    responsable_nombre: str | None
    fecha_compromiso: str | None
    status: str
    nudge: str
    token: str
    avances: list[AvanceItem]

class CompromisoPublicOut(BaseModel):  # vista del responsable (sin token ni datos del dueño)
    descripcion: str
    fecha_compromiso: str | None
    status: str
    avances: list[AvanceItem]

class AvanceIn(BaseModel):
    pct: int
    nota: str | None = None
    evidencia_url: str | None = None

class ResponsablePatch(BaseModel):
    responsable_email: str | None = None
    responsable_nombre: str | None = None
    fecha_compromiso: str | None = None   # iso date | None
```

### Endpoints del dueño (router nuevo `app/api/v1/pm/router.py`, prefix `/api/v1`, auth)
- **`GET /pm/compromisos`**: lista los `Compromiso` de `user_id` (orden por `created_at` desc).
  Por cada uno calcula `nudge` (ref_date = fecha del último avance o `created_at.date()`); devuelve
  `list[CompromisoOut]`.
- **`PATCH /pm/compromisos/{compromiso_id}`** (body `ResponsablePatch`): valida pertenencia (404 si
  no es del usuario); set de los campos provistos (`fecha_compromiso` se parsea de iso); devuelve
  `CompromisoOut`.

### Endpoints públicos SIN login (mismo router, sin `get_current_user_id`; credencial = token)
- **`GET /pm/c/{token}`**: busca por `token` (404 si no existe); devuelve `CompromisoPublicOut`
  (solo ese compromiso — el responsable nunca ve la minuta ni el resto).
- **`POST /pm/c/{token}/avance`** (body `AvanceIn`): 404 si token inválido; agrega
  `{fecha: today.isoformat(), pct, nota, evidencia_url}` a `avances` (`flag_modified`); actualiza
  `status`: `pct >= 100` → `"completado"`, `pct > 0` → `"en_progreso"` (no degrada un
  `"completado"`); devuelve `CompromisoPublicOut`.
- Registrar el router en `app/main.py` (`app.include_router(pm_router, prefix="/api/v1", tags=["pm"])`).

### Wiring en `POST /annual-plan/minuta/decision` (`cerrar_decision`)
Al cerrar A/B (además de escribir el compromiso en el tema de la minuta), crear un `Compromiso`:
```python
import secrets  # (top del módulo)
...
comp = Compromiso(
    user_id=user_id, descripcion=opcion, fecha_compromiso=(date.today() + timedelta(days=14)),
    status="abierto", token=secrets.token_urlsafe(16), avances=[],
    source={"month_id": str(active_month.id), "tema_id": body.tema_id},
)
db.add(comp)
await db.flush()
tema["compromiso"]["compromiso_id"] = str(comp.id)
```
(`comp.id` está disponible al construir por `default=uuid.uuid4`.) En "aplazar" no se crea nada.

## Frontend

- **Página pública** `frontend/src/app/c/[token]/page.tsx` (fuera de `/dashboard`, sin auth):
  `getCompromisoPublico(token)` + formulario (`% avance`, `nota`, `link de evidencia`, botón
  "marcar completado" = enviar pct 100). Usa un cliente axios sin token (o `api` sin interceptor de
  auth — el endpoint es público). Muestra los avances ya reportados.
- **`lib/pm.ts`**: tipos + `getCompromisos()`, `patchCompromiso(id, body)`,
  `getCompromisoPublico(token)`, `reportarAvance(token, body)`.
- **Tablero del dueño** `components/plan/CompromisosBoard.tsx`: lista cada compromiso con
  descripción, responsable, fecha, **chip de estado/nudge** (color sobrio por nivel), y botón
  **"copiar link"** (copia `${window.location.origin}/c/{token}` al portapapeles). Inputs para fijar
  responsable (email/nombre) → `patchCompromiso`.
- **Toggle del plan** (`app/dashboard/plan/page.tsx`): agregar pestaña **"Compromisos"** (Meses /
  Tablero de acuerdos / Cobertura / Minuta / **Compromisos**) → renderiza `<CompromisosBoard />`.

## Pruebas

Backend (pytest):
- `nudge_estado`: cada umbral (al_dia / recordatorio +7 / amarillo +14 / rojo +21 / vencido /
  completado).
- Modelo: construcción con campos; `token` único; registrado en `Base.metadata`.
- Wiring: cerrar decisión "A" crea un `Compromiso` (db mockeada: `db.add` recibe un Compromiso con
  `descripcion` = opción y `token`); "aplazar" no crea.
- Endpoints dueño: `GET /pm/compromisos` (lista con `nudge`), `PATCH` (set responsable; 404 ajeno).
- Endpoints públicos: `GET /pm/c/{token}` (200 / 404 token inválido), `POST .../avance`
  (agrega avance, `pct=100` → completado, `pct>0` → en_progreso).
- Migración: `create_compromisos` corre idempotente.
- Suite completa verde.

Frontend: `tsc --noEmit` + `npm run build` verdes; lint limpio en archivos nuevos.

## Criterio de "hecho"

- Cerrar A/B en la Minuta crea un Compromiso rastreable con token.
- El responsable abre `/c/{token}` (sin login) y reporta avance; el status se actualiza.
- El dueño ve el tablero de Compromisos con estado/nudge y copia el link.
- Sin envío de correo (V1); el dueño comparte el link a mano.
- Suite backend verde; build frontend verde; tabla `compromisos` creada en prod.

## Riesgos / decisiones abiertas

- Tabla nueva (correr `create_compromisos` en prod antes del deploy).
- Endpoints públicos sin auth: el token (`secrets.token_urlsafe(16)`, ~128 bits) es la credencial;
  no exponen datos del dueño ni de la minuta, solo el compromiso.
- Evidencia = link en V1 (no archivo); la subida real se añade con S3 después.
- Correo automático + scheduler diferidos (necesitan proveedor externo).
- El compromiso vive en su propia tabla; la minuta guarda `compromiso_id` para enlazar.
