# Roadmap alineado al template — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** El roadmap captura (opcionalmente) el contenido del template del cliente y su PDF se genera como deck 16:9.

**Architecture:** Se extiende el JSON del roadmap con campos opcionales que la IA llena solo si tiene evidencia; el PDF se reescribe como presentación apaisada con láminas condicionales; el frontend muestra/edita los campos nuevos con el patrón existente.

**Tech Stack:** FastAPI, anthropic tool-use (Opus), reportlab (landscape), Next.js 16 + Tailwind v4.

Spec: `docs/superpowers/specs/2026-07-13-roadmap-template-deck-design.md`

---

### Task 1: Esquema IA del roadmap (campos nuevos, opcionales)

**Files:**
- Modify: `backend/app/services/ai/roadmap.py`
- Test: `backend/tests/unit/test_roadmap_ai.py` (crear si no existe)

- [ ] **Step 1:** Test que, dado un `block.input` simulado con los campos nuevos, `generate_roadmap` los normaliza: `objetivos_estrategicos`, `key_enablers`, `temas_por_anio`, `conclusion_diagnostico`, `conclusion_entorno`, `anio_objetivo`, y por pilar `objetivo`, `estrategias`, `kpis` (con `meta` SIEMPRE `""`), `resultados_esperados`, `fases[anioN].titulo`.
- [ ] **Step 2:** Test que un roadmap de esquema viejo (sin campos nuevos) sigue devolviendo listas/strings vacíos y no revienta.
- [ ] **Step 3:** Extender `ROADMAP_TOOL.input_schema` con los campos nuevos (NO en `required`, salvo los que ya estaban). En la descripción de `kpis[].meta` y `metas_3anios[].target`: "DÉJALO VACÍO: lo fija el dueño. No inventes."
- [ ] **Step 4:** Extender `_SYSTEM`: el template es una guía; llena solo lo que puedas sustentar con la información dada; si no hay evidencia para un bloque, déjalo vacío. Explicar cada campo nuevo (objetivos estratégicos, key enablers, tema por año tipo "Ordenar la casa"/"Expandir"/"Consolidar", objetivo y estrategias por pilar, KPIs del pilar con valor actual, resultados esperados, título de cada fase).
- [ ] **Step 5:** Normalizar la salida en `generate_roadmap` (helpers `_norm_lista`, uno nuevo para kpis y otro para resultados). `anio_objetivo`: si la IA no lo da, `date.today().year + 3`. Forzar `kpis[].meta = ""`.
- [ ] **Step 6:** `_roadmap_fallback` devuelve las claves nuevas vacías (mismo shape).
- [ ] **Step 7:** `pytest tests/unit/test_roadmap_ai.py -v` verde. Commit.

---

### Task 2: PDF deck 16:9

**Files:**
- Modify: `backend/app/services/pdf/roadmap_pdf.py`
- Test: `backend/tests/unit/test_roadmap_pdf.py`

- [ ] **Step 1:** Tests: (a) roadmap completo → bytes que empiezan con `%PDF`; (b) roadmap vacío/`{}` → no lanza; (c) roadmap con esquema viejo (sin campos nuevos) → no lanza; (d) meta vacía → aparece "por definir" y nunca "None".
- [ ] **Step 2:** Reescribir `build_roadmap_pdf(roadmap, company_name)` con `pagesize=landscape(A4)`, una lámina por página:
  1. Portada (navy a sangre, nombre empresa, "Roadmap Estratégico al {anio_objetivo}", fecha). Hueco reservado para logo.
  2. Panorama (resumen_foda + conclusion_diagnostico) — omitir si ambos vacíos.
  3. Tendencias externas (resumen_entorno + conclusion_entorno) — omitir si vacíos.
  4. Lámina maestra: misión/visión, objetivos estratégicos, tarjetas de pilares (nombre, descripción, KPIs), estrategias clave por pilar, key enablers. Omitir bloques vacíos.
  5..N. Una lámina por pilar: objetivo, estrategias, plan de implementación (3 fases con título + acciones), KPIs actual→meta, resultados esperados. Omitir bloques vacíos.
  Última. Plan de ejecución: tabla pilares × 3 años con el tema del año como encabezado.
- [ ] **Step 3:** Colores: `_PILAR_COLORS` (sin cambios). Sin imágenes. Escapar todo el texto (`xml.sax.saxutils.escape`).
- [ ] **Step 4:** `pytest tests/unit/test_roadmap_pdf.py -v` verde. Commit.

---

### Task 3: Frontend — mostrar y editar los campos nuevos

**Files:**
- Modify: `frontend/src/lib/roadmap.ts` (tipos + `EMPTY`)
- Modify: `frontend/src/app/dashboard/plan/page.tsx`

- [ ] **Step 1:** Tipos: `KpiPilar {label, actual, meta}`, `ResultadoEsperado {titulo, descripcion}`, `Fase {titulo}`; extender `Pilar` con `objetivo?`, `estrategias?`, `kpis?`, `resultados_esperados?`, `fases?`; extender `Roadmap` con `anio_objetivo?`, `objetivos_estrategicos?`, `key_enablers?`, `temas_por_anio?`, `conclusion_diagnostico?`, `conclusion_entorno?`. Todos opcionales; `EMPTY` con valores vacíos.
- [ ] **Step 2:** En la vista Roadmap: bloque "Objetivos estratégicos" (lista) y "Key enablers" (chips) después de las metas; conclusiones bajo cada resumen. Bloques vacíos no se renderizan en modo lectura.
- [ ] **Step 3:** En cada tarjeta de pilar: objetivo, estrategias (lista), KPIs (`actual → meta`, "por definir" si vacía), resultados esperados. En el timeline "Recorrido a 3 años": mostrar el tema del año en el encabezado si existe.
- [ ] **Step 4:** Edición con el patrón existente (`EditControls`, `hide={validado}`): textarea por bloque, listas como una línea por ítem.
- [ ] **Step 5:** `npx eslint` limpio. Commit.
