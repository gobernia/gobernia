# Rediseño UX "for dummies" — Plan mes a mes + navegación superior (diseño)

Fecha: 2026-06-10
Estado: aprobado para escribir plan de implementación

## Contexto

El motor está completo (nodos 1-6 del pipeline en producción) pero la UI lo expone como un
"panel de ingeniero": la página del plan tiene 5 pestañas iguales (Meses / Tablero de acuerdos /
Cobertura / Minuta / Compromisos) + 3 paneles sueltos arriba (Diagnóstico, Agenda, Alertas), y
las tareas del mes están enterradas (mes → tarjeta de objetivo → tareas adentro). El usuario
pide estilo Monday, simple, "for dummies".

Decisiones de brainstorming (2026-06-10):
1. **El dashboard actual se queda como home** (`/dashboard`, intacto). "Sesión del mes" es una
   sección más.
2. **Navegación: barra horizontal ARRIBA** — Inicio · Sesión del mes · Plan · Compromisos.
3. **El kanban (`AcuerdosBoard`) se ELIMINA** — lo reemplaza la tabla Monday del mes.
4. Pantalla **mes por mes** (timeline arriba, abre en el mes activo) — patrón actual conservado.
5. Tabla Monday: filas = tareas, **agrupadas por objetivo** (como secciones de Monday), edición
   **inline** (responsable / fecha / estado-pastilla), candado de evidencia intacto.

**Solo frontend. Cero cambios de backend** (los endpoints existentes alimentan todo:
`updateTask` PATCH, evidencias, orden del día + PDF, agenda/minuta/alertas/compromisos).

Hechos verificados del codebase:
- No hay `layout.tsx` en `/dashboard` (cada página pinta su header). Hay rutas existentes:
  `/dashboard`, `/dashboard/plan`, `/dashboard/datos`, `/dashboard/sesion/[id]` (sesiones de
  consejo viejas — **NO tocar**; por eso la página nueva usa otra ruta).
- `plan/page.tsx`: monta `DiagnosticoPanel` (l.270), `AgendaPanel` (l.272), `AlertsPanel`
  (l.274), toggle de 5 vistas (l.277-307), `MonthTimeline` + `MonthDetail`, `ThemesPanel`
  (l.326), `TaskDrawer`, `CloseMonthModal`.
- `lib/annualPlan.ts` ya tiene `updateTask(id, patch)` (owner/status/due_date/…), `createTask`,
  `createObjective`, `updateObjective`, `deleteObjective`, `closeMonth`, `applyProposal`.
- Gate de evidencia en el front: `task.evidence_count === 0` bloquea pasar a `completada`
  (patrón de `AcuerdosBoard` l.86); el backend además responde 409.
- `MonthDetail.tsx` hoy: `OrdenDelDiaPanel` siempre visible + `ObjectiveCard`s (tareas adentro).

## Alcance

Reorganización frontend: barra de navegación, 2 páginas nuevas (composición de componentes
existentes), rediseño de la pantalla del mes con tabla Monday, y limpieza (pestañas + kanban).

**Fuera de alcance:** cambios de backend; rediseño del home (`/dashboard`); la página pública
`/c/[token]`; mejoras del Secretario/notificaciones; mobile-specific beyond lo razonable
(la tabla colapsa con scroll horizontal).

## 1. Navegación — `TopNav` + layout del dashboard

- `components/ui/TopNav.tsx` (client): barra horizontal con logo "GOBERNIA" (link a
  `/dashboard`) y 4 links: **Inicio** (`/dashboard`) · **Sesión del mes**
  (`/dashboard/sesion-del-mes`) · **Plan** (`/dashboard/plan`) · **Compromisos**
  (`/dashboard/compromisos`). Activo = por `usePathname()` (Inicio activo solo en match exacto
  de `/dashboard`; ojo: `/dashboard/sesion/[id]` no marca ninguno). Estilo sobrio de la marca
  (navy/bone); en pantallas chicas los links hacen scroll horizontal (`overflow-x-auto`).
- `app/dashboard/layout.tsx` (nuevo): renderiza `<TopNav />` + `{children}`. Los headers
  internos de las páginas existentes se conservan (no se tocan páginas fuera de alcance).

## 2. Página "Sesión del mes" — `/dashboard/sesion-del-mes`

`app/dashboard/sesion-del-mes/page.tsx` (client). Composición de componentes existentes, en
este orden:
1. Título: `Tu sesión de {Mes Año}` (mes activo — del status del plan o `new Date()`; usar
   `getAnnualPlanStatus()` best-effort: si 404 → mensaje "Genera tu plan primero" + link a Plan).
2. `<AgendaPanel />` (carta del Chair + agenda + botón convocar).
3. `<MinutaView />` (sesionar + decisiones A/B/Aplazar).
4. `<AlertsPanel />`.
Los tres componentes ya se auto-alimentan (fetch propio) — la página solo los compone.

## 3. Página "Compromisos" — `/dashboard/compromisos`

`app/dashboard/compromisos/page.tsx` (client): título "Compromisos" + `<CompromisosBoard />`
(ya se auto-alimenta).

## 4. Plan rediseñado — `/dashboard/plan`

### Se elimina
- El toggle de 5 vistas (`boardView`) y los branches de `tablero` / `cobertura` / `minuta` /
  `compromisos`.
- Los montajes de `AgendaPanel` y `AlertsPanel` (se mudaron a Sesión del mes).
- El componente `components/plan/AcuerdosBoard.tsx` (archivo borrado).

### Se queda (reacomodado)
- `DiagnosticoPanel` (compacto, arriba — sin cambios).
- `MonthTimeline` (abre en el mes activo — sin cambios).
- `TaskDrawer` y `CloseMonthModal` (sin cambios; el drawer sigue siendo el "ver detalle").
- `ThemesPanel` y `CoberturaBoard`: dentro de una sección colapsable **"Cobertura anual"**
  (cerrada por defecto) al final de la página — un `<details>`/estado con link discreto
  "Ver cobertura anual ▾".

### `MonthDetail` rediseñado
Estructura nueva (mismos props + los callbacks de tareas):
1. **Encabezado**: `{Mes Año} · Mes N` + foco + botón **"Orden del día ▾"** que colapsa/expande
   `OrdenDelDiaPanel` (cerrado por defecto; el PDF ya vive dentro del panel).
2. **Resumen del mes**: una fila de chips — objetivos (título corto de cada uno) y KPIs únicos
   (unión de `kpi_refs` de los objetivos, dedup, máx ~6). Solo lectura, de un vistazo.
3. **`<TasksTable />`** (nuevo — el corazón).
4. `MonthReviewPanel` si el mes está `done` (sin cambios).
5. Botones "Cerrar mes y revisar" + "Agregar objetivo" (sin cambios).
`ObjectiveCard` deja de usarse en `MonthDetail` (el archivo puede quedar, pero ya sin montar;
si ninguna otra vista lo usa, se borra).

### `components/plan/TasksTable.tsx` (nuevo)
Tabla estilo Monday, agrupada por objetivo:
- **Grupo** = objetivo: header con su título (editable con el mismo patrón rename actual:
  click/blur → `onRenameObjective`), menú ⋯ con "Eliminar objetivo" (→ `onDeleteObjective`),
  y al final del grupo una fila "+ Agregar tarea" (→ `onAddTask(objectiveId)`).
- **Columnas**: Tarea · Responsable · Vence · Estado · 📎.
  - **Tarea**: el título; click → `onTaskClick(task)` (abre el drawer de detalle).
  - **Responsable**: input de texto inline (defaultValue=owner; en blur si cambió →
    `updateTask(id, {owner})`); vacío muestra "➕ asignar" en gris.
  - **Vence**: `<input type="date">` inline (en change → `updateTask(id, {due_date})`).
  - **Estado**: pastilla de color (⚪ Pendiente / 🟡 En proceso / 🟢 Validado) que abre un
    `<select>`/menú con las 3 opciones. **Candado**: elegir "Validado" con
    `evidence_count === 0` NO llama al PATCH; muestra el aviso "Sube evidencia para validar"
    y abre el drawer (`onTaskClick`) donde está `EvidenceSection`. (El backend igual protege
    con 409.)
  - **📎**: el `evidence_count` si > 0.
- Optimistic update vía el callback `onPatchTask(taskId, patch)` que la página ya implementa
  para el drawer (reusar el mismo `patchTaskLocal`/handler existente para que el estado local
  se actualice igual).
- Vacío: "Este mes aún no tiene objetivos." (igual que hoy).
- Responsive: contenedor `overflow-x-auto`.

## 5. Limpieza

- Borrar `AcuerdosBoard.tsx` (y `ObjectiveCard.tsx` si nadie más lo importa).
- `npx tsc --noEmit` + `npm run build` + lint verdes; sin imports muertos.

## Criterio de "hecho"

- Barra superior con 4 destinos en todas las páginas del dashboard.
- `/dashboard/sesion-del-mes` muestra carta+agenda, minuta y alertas (lo del ritual junto).
- `/dashboard/compromisos` muestra el tablero de compromisos.
- `/dashboard/plan` = timeline + pantalla del mes con: orden del día colapsable (con PDF),
  resumen objetivos/KPIs, **tabla Monday con edición inline** (responsable/fecha/estado) y
  candado de evidencia; cobertura como sección colapsable; sin pestañas ni kanban.
- Build frontend verde; backend sin cambios (suite intacta).

## Riesgos / decisiones

- `/dashboard/sesion/[id]` (sesiones viejas) NO se toca; por eso la ruta nueva es
  `sesion-del-mes`.
- El layout añade la barra a TODAS las páginas del dashboard, incluidas las no rediseñadas
  (`/dashboard`, `/dashboard/datos`, `/dashboard/sesion/[id]`) — aceptable: solo agrega
  navegación consistente arriba.
- La edición inline reusa `updateTask`; si el PATCH falla, revertir el cambio local (patrón
  optimista con revert, como en cobertura B4).
