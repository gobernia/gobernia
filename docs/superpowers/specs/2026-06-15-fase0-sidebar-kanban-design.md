# Fase 0 — Sidebar + Kanban + limpieza del Plan — Diseño

**Fecha:** 2026-06-15
**Alcance:** Solo frontend (`frontend/`). Cero cambios de backend, de lógica de generación de plan, o de las compuertas de datos.

## Goal

Reestructurar la navegación y la vista del plan según el brief: convertir la barra superior en un menú lateral (sidebar) tipo dashboard, mover los 5 consejeros a una página propia "Tu consejo", devolver el kanban arrastrable como vista única de tareas del mes, quitar el botón "Agregar objetivo" y mostrar el orden del día legible debajo de las tareas.

## Architecture

La navegación del dashboard pasa de una `TopNav` horizontal fija (barra `h-12` arriba, `sticky top-0`) a un **`Sidebar` vertical fijo a la izquierda** (`fixed left-0`, ancho fijo en escritorio, colapsable con hamburguesa en móvil). El `dashboard/layout.tsx` envuelve las páginas y desplaza el contenido a la derecha del sidebar. Cada página del dashboard que hoy posiciona su header propio en `top-12` (para quedar debajo de la TopNav) pasa a `top-0` dentro de la columna de contenido, y las acciones "Mis datos" y "Salir" — hoy en headers de página — se consolidan en el pie del sidebar.

El kanban se recupera del historial de git (`AcuerdosBoard.tsx`, borrado en commit `9067d8e`) pero se **acota a un solo mes**: en vez de aplanar las tareas de los 12 meses, recibe los objetivos de un mes y muestra sus tareas en 3 columnas por estado. Reemplaza a `TasksTable` dentro de `MonthDetail`.

## Tech Stack

Next.js 16 (App Router; ver `frontend/AGENTS.md` — leer `node_modules/next/dist/docs/` antes de tocar routing/layout), TypeScript, Tailwind v4 (vars `--gob-navy`/`--gob-bone`/`--gob-ink`), framer-motion, @dnd-kit/core (drag-drop del kanban), lucide-react.

---

## Componente 1 — `Sidebar` (reemplaza `TopNav`)

**Crear:** `frontend/src/components/ui/Sidebar.tsx`
**Borrar:** `frontend/src/components/ui/TopNav.tsx` (recuperable de git si hace falta)

- `"use client"`, usa `usePathname()` para marcar el ítem activo (misma lógica `exact`/`startsWith` que la TopNav actual).
- Estructura: logo "GOBERNIA" arriba; lista de navegación; pie con "Datos" y "Salir".
- Items de navegación (con ícono lucide):
  | Ítem | href | exact | ícono |
  |---|---|---|---|
  | Inicio | `/dashboard` | sí | `Home` |
  | Sesión del mes | `/dashboard/sesion-del-mes` | no | `CalendarDays` |
  | Plan | `/dashboard/plan` | no | `ClipboardList` |
  | Compromisos | `/dashboard/compromisos` | no | `CheckSquare` |
  | Tu consejo | `/dashboard/consejo` | no | `Users` |
- Pie (siempre visible, separado con borde superior):
  - "Datos" → `Link` a `/dashboard/datos` (ícono `Settings`).
  - "Salir" → `button` con `supabase.auth.signOut()` + redirect a `/` (ícono `LogOut`). Reutiliza el patrón de `handleSignOut` que hoy vive en `dashboard/page.tsx`.
- **Escritorio:** `fixed left-0 top-0 h-dvh w-60` (240px), fondo `--gob-navy`, texto `--gob-bone` (misma paleta que la TopNav actual).
- **Móvil:** oculto por defecto; botón hamburguesa fijo arriba-izquierda que abre el sidebar como overlay (con backdrop). Cierra al navegar o al tocar el backdrop. Estado local `useState`.
- Ítem activo: fondo/borde resaltado (adaptar el `border-b-2` actual a un indicador vertical, p. ej. `border-l-2` o fondo translúcido).

## Componente 2 — `dashboard/layout.tsx`

**Modificar:** `frontend/src/app/dashboard/layout.tsx`

- Cambia de envolver `<TopNav />` a envolver `<Sidebar />`.
- El contenedor de `children` recibe margen izquierdo en escritorio igual al ancho del sidebar: `md:ml-60`. En móvil sin margen (sidebar es overlay).

```tsx
import Sidebar from "@/components/ui/Sidebar"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh">
      <Sidebar />
      <div className="md:ml-60">{children}</div>
    </div>
  )
}
```

## Componente 3 — Migración de headers de página (`top-12` → `top-0`)

Al desaparecer la barra superior `h-12`, las páginas que hoy posicionan su header propio en `top-12` y empujan el contenido con `pt-26` deben recalcularse a `top-0` / `pt-14` (alto del header propio), y respetar la columna de contenido (no `inset-x-0` de viewport completo, sino dentro del `md:ml-60`).

Archivos afectados (todos bajo `frontend/src/app/dashboard/`):
- `page.tsx` (Inicio) — header `fixed top-12` (línea ~212), `main pt-26` (~389). Además: **quitar de su header propio** los enlaces "Mis datos" y "Salir" (ahora viven en el sidebar); el header de Inicio queda solo con el logo (o se elimina si queda vacío y el logo ya está en el sidebar).
- `datos/page.tsx` — header `fixed top-12` (~73), `main pt-26` (~83).
- `sesion/[id]/page.tsx` — header `fixed top-12` (~235) y barra `fixed top-14` (~265).

Páginas que **no** dependían de la TopNav (no cambian su offset, solo heredan el `md:ml-60` del layout):
- `sesion/[id]/plan/page.tsx` — usa `top-0` propio (~543).
- `compromisos/page.tsx`, `sesion-del-mes/page.tsx`, `plan/page.tsx` — verificar en implementación que no asuman el offset de la TopNav; ajustar solo si rompen.

**Regla general:** donde hubiera `top-12` por la TopNav, usar `top-0`; donde el header propio sea redundante con el sidebar, simplificarlo. El detalle exacto por archivo lo resuelve el plan de implementación leyendo cada uno.

## Componente 4 — Página "Tu consejo"

**Crear:** `frontend/src/app/dashboard/consejo/page.tsx`
**Modificar:** `frontend/src/app/dashboard/page.tsx` (quitar la sección de consejeros)

- Mover el array `AGENTS` (los 5 consejeros) y la sección de tarjetas "Agents" (líneas ~585-628 de `dashboard/page.tsx`) a la página nueva.
- La página "Tu consejo" muestra las 5 tarjetas (Finanzas, Estrategia, Riesgos, Auditoría, Independiente) con el mismo diseño. El botón "Iniciar sesión" de cada tarjeta conserva su comportamiento (`tryCreateSession` → modal de nueva sesión o modal de setup según `onboardingComplete`).
- El modal de "Nueva sesión" y el de "Configura tu empresa" que hoy viven en `dashboard/page.tsx` se necesitan también aquí porque el botón los dispara. Opción de implementación: extraer ese estado/modales a un componente reutilizable, o duplicar el flujo mínimo. El plan decide; preferir extracción si es limpio.
- En `dashboard/page.tsx` (Inicio) se elimina la sección de consejeros; el resto (saludo, score, checklist, plan, sesiones) permanece.

## Componente 5 — Kanban del mes (reemplaza `TasksTable`)

**Crear:** `frontend/src/components/plan/MonthKanban.tsx` (adaptado de `AcuerdosBoard` recuperado de git `9067d8e^`)
**Modificar:** `frontend/src/components/plan/MonthDetail.tsx`

- Recuperar `AcuerdosBoard.tsx` del historial: `git show 9067d8e^:frontend/src/components/plan/AcuerdosBoard.tsx`. Sirve de base: 3 columnas (`pendiente` "Pendiente", `en_progreso` "En proceso", `completada` "Validado"), drag-drop con @dnd-kit, tarjetas con título/prioridad/owner/conteo de evidencia.
- **Adaptación clave:** el original recibía el `AnnualPlan` completo y aplanaba tareas de todos los meses (cada tarjeta etiquetaba su mes). El nuevo `MonthKanban` recibe **los objetivos de un solo mes** y muestra sus tareas; sin etiqueta de mes en la tarjeta.
- Props: `objectives` (del mes), `onTaskClick(task)` (abre detalle/edición), `onUpdateTask(taskId, patch)` (para cambiar `status` al soltar en otra columna). Reutiliza los handlers que `MonthDetail` ya recibe y pasa hoy a `TasksTable`.
- Al soltar una tarjeta en otra columna → `onUpdateTask(taskId, { status: columnaDestino })` (update optimista, igual que hoy).
- En `MonthDetail.tsx`: reemplazar el bloque `<TasksTable .../>` (líneas ~78-85) por `<MonthKanban .../>`. `TasksTable` deja de importarse/usarse en `MonthDetail` (el archivo `TasksTable.tsx` puede quedarse en el repo por si se reusa, pero no se referencia desde la vista del mes).

## Componente 6 — Quitar botón "Agregar objetivo"

**Modificar:** `frontend/src/components/plan/MonthDetail.tsx`

- Eliminar el `<button>` "Agregar objetivo" (líneas ~96-101) y la prop/handler `onAddObjective` si queda sin uso tras quitarlo. Rastrear el call-site en `plan/page.tsx` y limpiar la cadena (handler + prop) para no dejar código muerto.

## Componente 7 — Orden del día legible, debajo de las tareas

**Modificar:** `frontend/src/components/plan/MonthDetail.tsx`

- Hoy el orden del día es un botón-toggle arriba (líneas ~48-58) que muestra `OrdenDelDiaPanel` colapsado.
- Mover `OrdenDelDiaPanel` a **debajo del kanban** (después de `MonthKanban`, antes o después del botón "Cerrar mes").
- Mostrarlo **expandido por defecto**, dentro de una sección con encabezado claro ("Orden del día"), con opción de colapsar. Quitar el botón-toggle del header del mes.

---

## Out of scope (NO se toca)

- Backend completo (Python/FastAPI/Celery), generación de plan, compuertas de datos.
- Páginas "Sesión del mes" y "Compromisos" salvo el ajuste de offset si el sidebar lo requiere.
- `TasksTable.tsx` no se borra (puede reutilizarse luego); solo se desconecta de la vista del mes.

## Testing

Frontend sin suite de pruebas unitarias para componentes de UI. Verificación:
1. `npm run build` (o `next build`) pasa sin errores de tipos.
2. Smoke manual en local: navegación por el sidebar (escritorio y móvil), página "Tu consejo" muestra los 5 consejeros y su botón funciona, vista del mes muestra el kanban arrastrable con cambio de estado al soltar, no aparece "Agregar objetivo", orden del día visible y legible debajo de las tareas, headers de las páginas migradas no se enciman ni dejan hueco.

## Dependencias / orden de implementación sugerido

1. `Sidebar` + `layout.tsx` (la base de navegación).
2. Migración de headers de página (`top-12` → `top-0`) — depende de (1).
3. Página "Tu consejo" + limpieza de Inicio.
4. `MonthKanban` + reemplazo en `MonthDetail`.
5. Quitar "Agregar objetivo".
6. Orden del día debajo de las tareas.

(2) puede solaparse con (1). (3)-(6) son independientes entre sí una vez hecho (1).
