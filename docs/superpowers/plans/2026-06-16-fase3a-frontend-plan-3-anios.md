# Fase 3A (Frontend) — Plan estratégico a 3 años — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rediseñar la página del plan para el plan estratégico a N años: roadmap de hitos arriba, tareas del mes con "Necesita: {documento}", orden del día como resumen de tareas, selector 1/2/3 al generar, y ocultar Sesiones/Minutas del menú.

**Architecture:** Reusa la página `/dashboard/plan` y sus componentes (MonthTimeline, MonthDetail, MonthKanban de Fase 0). Se agrega un `MilestoneRoadmap` que lee `plan.milestones` (solo lectura). El cliente API gana los tipos nuevos y manda `horizon_years` al generar. El backend de la Fase 3A (en la misma rama) ya expone `milestones`, `horizon_years` y `required_doc`.

**Tech Stack:** Next.js 16 App Router, TypeScript, framer-motion, lucide-react, axios vía `@/lib/api`, Tailwind v4.

**Verificación:** Sin suite de UI. Gate: `npm run lint` + `npm run build` (sin errores nuevos) + smoke. Comandos desde `frontend/`. Errores de lint preexistentes (`datos/page.tsx`, `sesion/[id]/plan/page.tsx`, `onboarding/`) están fuera de alcance.

---

### Task 1: Tipos del cliente + generar con horizonte

**Files:**
- Modify: `frontend/src/lib/annualPlan.ts`

- [ ] **Step 1: Agregar tipos y el horizonte al cliente**

En `frontend/src/lib/annualPlan.ts`:
- Agregar la interfaz `Milestone` (cerca de las otras interfaces):
```ts
export interface Milestone {
  type: "trimestral" | "semestral" | "anual"
  year: number
  period: number
  title: string
  target: string
  kpi_ref: string | null
}
```
- En la interfaz `Task`, agregar el campo:
```ts
  required_doc: string | null
```
- En la interfaz `AnnualPlan`, agregar:
```ts
  horizon_years: number
  milestones: { items: Milestone[] } | null
```
- Cambiar `generateAnnualPlan` para que acepte y mande el horizonte (hoy no recibe args y hace `api.post("/annual-plan/generate")`):
```ts
export async function generateAnnualPlan(horizonYears: number = 3): Promise<AnnualPlanStatus> {
  const r = await api.post<AnnualPlanStatus>("/annual-plan/generate", { horizon_years: horizonYears })
  return r.data
}
```

- [ ] **Step 2: lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: pasan (los componentes que usan `Task`/`AnnualPlan` siguen compilando; los campos nuevos son opcionales en uso).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/annualPlan.ts
git commit -m "feat(fase3a-fe): tipos Milestone/required_doc/horizon_years + generate(horizonYears)"
```

---

### Task 2: `MilestoneRoadmap` + roadmap/selector en la página del plan

**Files:**
- Create: `frontend/src/components/plan/MilestoneRoadmap.tsx`
- Modify: `frontend/src/app/dashboard/plan/page.tsx`

- [ ] **Step 1: Crear `MilestoneRoadmap.tsx`**

```tsx
"use client"

import type { AnnualPlan } from "@/lib/annualPlan"

const TYPE_LABEL: Record<string, string> = { trimestral: "Trimestre", semestral: "Semestre", anual: "Año" }

export default function MilestoneRoadmap({ milestones }: { milestones: AnnualPlan["milestones"] }) {
  const items = milestones?.items ?? []
  if (items.length === 0) return null
  const years = Array.from(new Set(items.map(m => m.year))).sort((a, b) => a - b)
  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Roadmap estratégico</p>
        <h2 className="text-xl font-bold text-black tracking-tight">Tus hitos</h2>
      </div>
      <div className="space-y-5">
        {years.map(year => (
          <div key={year} className="space-y-2">
            <p className="text-[10px] uppercase tracking-wide text-gray-400 font-medium">Año {year}</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {items.filter(m => m.year === year).map((m, i) => (
                <div key={i}
                  className={`rounded-xl border p-3 space-y-1 ${m.type === "anual" ? "border-[var(--gob-navy)] bg-[var(--gob-navy)]/[0.03]" : "border-gray-100"}`}>
                  <p className="text-[10px] uppercase tracking-wide text-gray-400 font-medium">
                    {TYPE_LABEL[m.type] ?? m.type}{m.type !== "anual" ? ` ${m.period}` : ""}
                  </p>
                  <p className="text-sm font-medium text-black leading-snug">{m.title}</p>
                  {m.target && <p className="text-xs text-gray-500 leading-snug">{m.target}</p>}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Insertar el roadmap + selector de horizonte en `plan/page.tsx`**

1. Importar el componente (junto a los otros imports de `@/components/plan/...`):
```tsx
import MilestoneRoadmap from "@/components/plan/MilestoneRoadmap"
```
2. Agregar un estado de horizonte cerca de los otros `useState` del componente `AnnualPlanPage`:
```tsx
  const [horizonYears, setHorizonYears] = useState(3)
```
3. En el handler `onGenerate` (hoy hace `await generateAnnualPlan()`), pasar el horizonte: `await generateAnnualPlan(horizonYears)`.
4. En el estado vacío (la vista `none`/`failed`/`error`, donde está el botón que llama `onGenerate(isFail)`), agregar — SOLO cuando NO es estado de datos-faltantes y cuando es la primera generación (no regenerar) — un mini-selector arriba del botón. Insertarlo justo antes del `<button onClick={() => onGenerate(isFail)}>`:
```tsx
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs text-gray-400">Horizonte:</span>
                {[1, 2, 3].map(y => (
                  <button key={y} type="button" onClick={() => setHorizonYears(y)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border-2 transition-colors ${
                      horizonYears === y
                        ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                        : "border-gray-100 text-gray-500 hover:border-gray-300"}`}>
                    {y} año{y > 1 ? "s" : ""}{y === 3 ? " ·rec" : ""}
                  </button>
                ))}
              </div>
```
   (Leer el bloque del estado vacío para colocarlo en el contenedor correcto; el selector solo tiene sentido cuando se va a generar, no en el caso `isDatos`. Si el layout del estado vacío lo complica, colocarlo dentro del mismo contenedor centrado, antes del botón de "Generar/Reintentar".)
5. En la vista activa (después de `view === "active"`), insertar el roadmap **entre** `MonthTimeline` y `MonthDetail`. Hoy:
```tsx
        {plan && (
          <MonthTimeline months={plan.months} selectedIndex={selectedMonth} onSelect={setSelectedMonth} />
        )}
        {month && ( <MonthDetail ... /> )}
```
   Insertar entre ambos:
```tsx
        {plan?.milestones && <MilestoneRoadmap milestones={plan.milestones} />}
```
6. El título de la vista activa hoy usa un fallback `"Plan de 12 meses"`. Cambiarlo para usar el título real del backend (que ahora es "Plan estratégico de N año(s)"): `{plan?.title ?? "Plan estratégico"}`.

- [ ] **Step 3: lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: pasan. La ruta `/dashboard/plan` compila; el roadmap aparece cuando hay `milestones`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/plan/MilestoneRoadmap.tsx frontend/src/app/dashboard/plan/page.tsx
git commit -m "feat(fase3a-fe): roadmap de hitos + selector de horizonte 1/2/3"
```

---

### Task 3: "Necesita: {documento}" en la tarjeta + orden del día como resumen de tareas

**Files:**
- Modify: `frontend/src/components/plan/MonthKanban.tsx`
- Modify: `frontend/src/components/plan/MonthDetail.tsx`

- [ ] **Step 1: Mostrar `required_doc` en la tarjeta del kanban**

En `frontend/src/components/plan/MonthKanban.tsx`, dentro del componente `Card` (la tarjeta de tarea), después del `<div>` que muestra prioridad/owner/evidencia, agregar (cuando la tarea pide documento):
```tsx
      {task.required_doc && (
        <p className="text-[10px] text-amber-600 bg-amber-50 rounded px-1.5 py-0.5 inline-block">
          Necesita: {task.required_doc}
        </p>
      )}
```
(El tipo `Task` ya tiene `required_doc` tras Task 1. `task` es la prop de `Card`.)

- [ ] **Step 2: Cambiar el orden del día a un resumen de las tareas del mes**

En `frontend/src/components/plan/MonthDetail.tsx`, la sección "Orden del día" hoy renderiza `<OrdenDelDiaPanel monthIndex={month.month_index} />` (el motor de señales, que estamos dejando de usar en este flujo). Reemplazar ESE contenido por un resumen de los títulos de las tareas del mes (derivado de `month.objectives`, sin fetch):

1. Quitar el import `import OrdenDelDiaPanel from "@/components/plan/OrdenDelDiaPanel"`.
2. Antes del `return`, derivar el resumen:
```tsx
  const taskTitles = month.objectives.flatMap(o => o.tasks.map(t => t.title))
```
3. Reemplazar el cuerpo de la sección "Orden del día" (lo que hoy renderiza `<OrdenDelDiaPanel ... />`) por:
```tsx
            {taskTitles.length > 0 ? (
              <ul className="space-y-1.5">
                {taskTitles.map((t, i) => (
                  <li key={i} className="text-sm text-gray-700 flex gap-2">
                    <span className="text-gray-300">{i + 1}.</span>{t}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-300 italic">Sin tareas este mes.</p>
            )}
```
   (Mantener el contenedor colapsable de "Orden del día" que ya existe de Fase 0; solo cambia su contenido interno.)

- [ ] **Step 3: lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: pasan. `OrdenDelDiaPanel` puede quedar sin usar como archivo (no se borra; solo se desconecta de `MonthDetail`).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/plan/MonthKanban.tsx frontend/src/components/plan/MonthDetail.tsx
git commit -m "feat(fase3a-fe): 'Necesita: documento' en tarjeta + orden del día = resumen de tareas"
```

---

### Task 4: Ocultar Sesiones y Minutas del menú

**Files:**
- Modify: `frontend/src/components/ui/Sidebar.tsx`

- [ ] **Step 1: Quitar el ítem "Sesión del mes" del sidebar**

En `frontend/src/components/ui/Sidebar.tsx`, en el array `LINKS`, eliminar la entrada de "Sesión del mes" (`{ href: "/dashboard/sesion-del-mes", ... }`). Quitar también el ícono `CalendarDays` del import de lucide si queda sin uso (lo indicará `npm run lint`). El array `LINKS` queda: Inicio · Plan · Diagnóstico · Compromisos · Tu consejo.

> La página `/dashboard/sesion-del-mes` y la vista de minuta NO se borran (quedan en el código, solo sin entrada en el menú) — una decisión futura puede reactivarlas.

- [ ] **Step 2: lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: pasan, sin imports sin usar introducidos.

- [ ] **Step 3: Smoke (referencia)**

El menú lateral ya no muestra "Sesión del mes". El plan muestra el roadmap de hitos arriba, las tareas del mes con "Necesita: …" cuando aplica, y el orden del día como lista de tareas.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Sidebar.tsx
git commit -m "feat(fase3a-fe): ocultar 'Sesión del mes' del menú"
```

---

## Self-Review (cobertura del spec — Componente 4)

- **Cliente: tipos `Milestone`/`milestones`/`horizon_years`/`required_doc` + generate(horizonYears)** → Task 1. ✅
- **Roadmap de hitos arriba (solo lectura)** → Task 2 (`MilestoneRoadmap`, insertado entre timeline y detail). ✅
- **Selector 1/2/3 (default 3) al generar** → Task 2. ✅
- **Título dinámico** → Task 2. ✅
- **"Necesita: {required_doc}" en la tarea** → Task 3 (tarjeta del kanban). ✅
- **Orden del día = resumen de tareas del mes** → Task 3 (MonthDetail). ✅
- **Ocultar Sesiones/Minutas** → Task 4. ✅

Consistencia: `Milestone`/`AnnualPlan.milestones` (`{items: Milestone[]}`) coinciden con lo que devuelve el backend (`plan.milestones = {"items":[...]}`). `Task.required_doc` coincide con `ActionTaskOut.required_doc`. `generateAnnualPlan(horizonYears)` manda `{horizon_years}` que el backend valida 1-3. El roadmap solo se muestra si hay `milestones` (planes viejos sin hitos no rompen).
