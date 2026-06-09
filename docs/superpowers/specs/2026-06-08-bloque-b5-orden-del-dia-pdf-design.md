# Bloque B5 — Orden del día en PDF (diseño)

Fecha: 2026-06-08
Estado: aprobado para escribir plan de implementación

## Contexto

Quinto sub-proyecto del Motor de Cobertura del Consejo. B1–B4 ya están en producción.
El brief pide que la orden del día se pueda **leer en el dashboard y descargar en PDF**.
B2 ya entrega la orden del día (temas programados + objetivos del mes); B4 agregó qué temas
están cubiertos (`covered_keys`). B5 la hace **descargable como PDF**.

Hechos del codebase:
- `GET /annual-plan/months/{m}/orden-del-dia` (`get_orden_del_dia` en
  `app/api/v1/annual_plan/router.py`) computa: plan → themes → month(objectives) →
  `scheduled_for_session` → `OrdenDelDiaOut` (permanent_themes, coverage_themes, objectives,
  covered_keys).
- **No hay librería de PDF instalada.** Decisión: **reportlab** (pure-python, corre en
  Railway sin libs de sistema).
- El nombre de empresa vive (best-effort) en `OnboardingSession.memory_buffer["company"]`.

## Alcance de B5

Generar el **PDF de la Orden del Día** de un mes y un botón "Descargar PDF" en el panel.

**Fuera de alcance de B5**: branding/plantilla elaborada, PDF de otros tableros (cobertura/
acuerdos), envío por email, alertas (B6).

## Backend

### Dependencia
Agregar `reportlab` a `backend/requirements.txt` (e instalarlo en el venv local para correr
tests). Pure-python.

### Refactor (limpieza al tocar el código)
La computación de la orden del día está inline en `get_orden_del_dia`. Extraerla a un helper
`async def _build_orden_data(plan, month_index, db) -> dict | None` que devuelve un dict con
`{month_index, period_year, period_month, permanent_themes, coverage_themes, covered_keys,
objectives}` (los `permanent_themes`/`coverage_themes` como `ThemeRef`; `objectives` como
`ObjectiveOut`), o `None` si el mes no existe. Ambos endpoints (JSON y PDF) lo usan → sin
duplicar lógica. `get_orden_del_dia` arma `OrdenDelDiaOut(**data)`.

### Servicio PDF
`app/services/pdf/orden_del_dia_pdf.py`:
```
def build_orden_pdf(data: dict, company_name: str | None) -> bytes
```
Usa reportlab (platypus: `SimpleDocTemplate` sobre `BytesIO`, `Paragraph`/`Spacer`). Contenido:
- **Encabezado**: `company_name` si viene, si no "Plan estratégico de 12 meses"; debajo,
  **"Orden del día — {Mes} {Año} · Sesión {month_index}"** (nombre de mes en español desde
  `_MONTH_NAMES`/`MONTH_NAMES`).
- **Temas del Consejo**: subtítulos "Permanentes" y "Cobertura"; cada tema en una línea;
  los que están en `covered_keys` se marcan con un "✓" al inicio (o "(cubierto)").
- **Objetivos del mes**: por objetivo, su `title` y, si tiene, sus `kpi_refs` en gris.
- **Pie**: "Generado por Gobernia · {fecha de hoy}".
Devuelve los bytes del PDF.

### Endpoint
`GET /annual-plan/months/{month_index}/orden-del-dia/pdf`:
- Resuelve el plan (`_current_plan`); 404 si no hay.
- `data = await _build_orden_data(plan, month_index, db)`; 404 si `None`.
- `company_name` best-effort: consulta la `OnboardingSession` del usuario y lee
  `memory_buffer.get("company", {}).get("name")` (try/except → `None` si falla).
- `pdf = build_orden_pdf(data, company_name)`.
- Devuelve `Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition":
  'attachment; filename="orden-del-dia-mes-{month_index}.pdf"'})`.

## Frontend

En `lib/ordenDelDia.ts`, una función de descarga:
```typescript
export async function downloadOrdenPdf(monthIndex: number): Promise<void>
```
que hace `api.get(`/annual-plan/months/${monthIndex}/orden-del-dia/pdf`, { responseType: "blob" })`
(el interceptor de `api` agrega el token), crea un `URL.createObjectURL(blob)`, dispara la
descarga con un `<a download="orden-del-dia-mes-{m}.pdf">` temporal, y revoca el URL.

En `OrdenDelDiaPanel.tsx`, un botón **"Descargar PDF"** (junto al título "Orden del día") que
llama `downloadOrdenPdf(monthIndex)` (con estado `downloading` para deshabilitar mientras baja).

## Pruebas

Backend:
- `build_orden_pdf`: con un `data` mínimo, devuelve `bytes` que empiezan con `b"%PDF"`.
- Endpoint PDF: 200 + `content-type` `application/pdf` + body no vacío (db mockeada; el
  `_build_orden_data` se ejerce con los mocks del patrón existente).
- El refactor no rompe `get_orden_del_dia` (el test existente sigue verde).
- Suite completa verde, sin regresiones.

Frontend: `tsc --noEmit` + `npm run build` verdes; lint limpio en archivos nuevos.

## Criterio de "hecho" para B5

- `reportlab` en requirements; `GET .../orden-del-dia/pdf` devuelve un PDF descargable.
- El dueño descarga el PDF de la orden del día desde el panel.
- Suite backend verde; build frontend verde.

## Riesgos / decisiones abiertas

- Sin migración (no toca DB).
- Plantilla simple (sin logo/branding); se puede enriquecer después.
- `reportlab` debe quedar en `requirements.txt` para que Railway lo instale en el deploy.
