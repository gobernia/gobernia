# Roadmap Estratégico (documento ejecutivo del plan a 3 años) — Diseño

**Fecha:** 2026-07-06
**Estado:** Aprobado por el usuario, listo para plan de implementación.

## Objetivo

Elevar el output del plan a 3 años (hoy: lista de tareas Camino/Timeline) a un **documento
ejecutivo tipo Roadmap Estratégico**: claro, coherente e inspirador, que el dueño/directivos usen
para comunicación interna, gobernanza e inversión de recursos. Es el deliverable más importante de
la plataforma.

## Reencuadre (decisión del usuario)

El Roadmap **NO es una función nueva separada**: es el **mismo plan a 3 años que ya se genera tras el
FODA** (mismo disparador "Generar mi plan a 3 años"), pero con el **output estructurado como
documento ejecutivo**. No se agregan pasos ni preguntas nuevas al onboarding. El Camino/Timeline
mes a mes que ya existe queda como la **capa de ejecución** debajo del Roadmap. (El "Plan de Trabajo
12 meses" con estructura SMART/PM es un deliverable aparte, se diseñará después.)

## Decisiones (del brainstorm)

1. **Relación con el plan actual:** Roadmap arriba (estrategia) → Camino/Timeline actual = ejecución.
2. **Generación:** la IA redacta un **borrador editable** desde los datos que YA existen (empresa,
   KPIs que Todd capturó, visión, diagnóstico interno, FODA, entorno/factores externos, metas). Sin
   captura nueva.
3. **Metas a 3 años:** la IA propone la dirección de cada meta usando los KPIs reales; si hay valor
   actual lo pone como base; el usuario fija/edita el target. Nada inventado (no se fabrican números).

## Estructura del Roadmap

1. **Encabezado ejecutivo:**
   - Visión (de `vision.statement` si existe; la IA la pule).
   - Misión (IA la redacta desde el contexto de la empresa).
   - Propuesta de valor (IA, desde diagnóstico/FODA).
   - Metas a 3 años: lista de `{meta, kpi, valor_actual, target}` — dirección propuesta por IA;
     `target` editable por el usuario.
   - Resumen FODA (síntesis ejecutiva de la matriz).
   - Resumen del entorno (oportunidades y amenazas clave que conducen la estrategia).
2. **Pilares estratégicos (3-5):** derivados del FODA/diagnóstico (ej. Excelencia operacional,
   Expansión de mercado, Innovación). Cada pilar: `{nombre, descripcion}`.
3. **Milestones por pilar × año (Año 1 / Año 2 / Año 3):** tangibles y medibles, 2-4 por celda.

## Arquitectura

### Datos
- **Columna nueva `annual_plans.roadmap`** (JSONB, nullable), creada con `scripts/alter_plan_roadmap.py`
  (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS roadmap JSONB`) — NO Alembic ([[prod_schema_no_alembic]]).
- Forma del JSON:
  ```json
  {
    "vision": "string",
    "mision": "string",
    "propuesta_valor": "string",
    "metas_3anios": [{"meta": "str", "kpi": "str|null", "valor_actual": "str|null", "target": "str|null"}],
    "resumen_foda": "string",
    "resumen_entorno": "string",
    "pilares": [
      {"nombre": "str", "descripcion": "str",
       "milestones": {"anio1": ["..."], "anio2": ["..."], "anio3": ["..."]}}
    ]
  }
  ```

### Backend
- **Generador:** `app/services/ai/roadmap.py` → `generate_roadmap(memory_buffer, diagnostico_content) -> dict`.
  - Opus tool-use (sin web), espejo de `foda.py`. Lee: `company`, `kpis`, `vision` del memory_buffer;
    `fortalezas_debilidades`, `riesgos`, `foda`, `factores_externos`, `metas_orden` del diagnóstico.
  - Deriva Pilares del FODA/diagnóstico; propone metas con base en KPIs (valor actual si existe,
    target vacío para que el usuario lo fije); redacta visión/misión/propuesta de valor y resúmenes.
  - Fallback determinista `_roadmap_fallback(...)` (sin API key): visión de `vision.statement`,
    pilares desde los cuadrantes del FODA, metas desde los KPIs con valor, milestones vacíos.
- **Wire-up:** en `app/tasks/annual_plan_tasks.py::_run_generation`, tras construir el plan, generar
  el roadmap (`generate_roadmap`) y guardarlo en `plan.roadmap`. Se genera en la misma corrida que el
  plan (mismo botón), sin re-correr nada.
- **Endpoints** (en `app/api/v1/annual_plan/router.py`):
  - `GET /annual-plan/roadmap` → devuelve `plan.roadmap` (o 404 si no hay plan / `{}` si aún no).
  - `PATCH /annual-plan/roadmap` → reemplaza el `roadmap` (edición del usuario, guardado completo del
    documento editado). Valida propiedad por `user_id`.
- **PDF:** `app/services/pdf/roadmap_pdf.py` → `build_roadmap_pdf(roadmap, company_name)` + endpoint
  `GET /annual-plan/roadmap/pdf` (espejo de `foda_pdf`). Documento ejecutivo: encabezado, metas,
  pilares con milestones por año.

### Frontend
- **Vista Roadmap en `dashboard/plan/page.tsx`:** el toggle actual (Camino/Timeline) gana una 3ª
  opción **"Roadmap"**, que es la vista **por defecto**. Muestra el documento ejecutivo con el estilo
  de marca (tokens `--gob-*`), secciones claras y jerarquía; botón **PDF**.
- **Edición por sección:** cada sección editable (visión, misión, propuesta de valor, metas/targets,
  pilares, milestones) con un modo edición inline → `PATCH /annual-plan/roadmap` (guarda el documento
  completo). UX simple: botón "Editar" por bloque → inputs → "Guardar".
- **lib:** `lib/roadmap.ts` (o extender `lib/annualPlan.ts`) con tipos + `getRoadmap`, `saveRoadmap`,
  `downloadRoadmapPdf`.
- El **Camino/Timeline** existente queda igual, como ejecución bajo el Roadmap.

## Alcance v1 (YAGNI)
**Incluye:** generación IA del Roadmap (borrador editable) tras el FODA, vista ejecutiva + edición por
sección + PDF, pilares 3-5 derivados, metas con base en KPIs + target editable, milestones por pilar×año.

**Deja fuera (después):** el "Plan de Trabajo 12 meses" (SMART + gestión de proyecto); versionado/histórico
del roadmap; regeneración parcial por sección; métricas de avance sobre milestones.

## Pruebas
- **Unit:** `_roadmap_fallback` produce la estructura completa (pilares desde FODA, metas desde KPIs,
  sin inventar targets); `generate_roadmap` sin API key usa fallback; el generador tolera diagnóstico/
  FODA vacíos sin truncar; `build_roadmap_pdf` con roadmap completo/vacío devuelve `%PDF-` sin truenos.
- **Integración:** `GET /annual-plan/roadmap` devuelve el roadmap del plan del usuario (404 sin plan);
  `PATCH /annual-plan/roadmap` guarda y respeta propiedad; el PDF responde `application/pdf`.

## Despliegue
- `scripts/alter_plan_roadmap.py` en prod (con autorización humana).
- Push a **ambos remotos** (origin=web/Vercel, cbeuvrin=worker/Railway).
