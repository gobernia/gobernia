# Fase 0 — Sidebar + Kanban + limpieza del Plan — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir la navegación del dashboard en un sidebar lateral, mover los consejeros a su página, devolver el kanban arrastrable como vista del mes, y limpiar la vista del plan — todo solo en frontend.

**Architecture:** La `TopNav` horizontal se reemplaza por un `Sidebar` vertical fijo a la izquierda (`fixed left-0 w-60`, colapsable en móvil); el `layout` desplaza el contenido con `md:ml-60`. Los headers de página que compensaban la TopNav (`top-12`, `pt-26`) se recalculan y se desplazan a la derecha del sidebar (`md:left-60`). El kanban (`MonthKanban`, recuperado de git y acotado a un mes) reemplaza a `TasksTable` dentro de `MonthDetail`.

**Tech Stack:** Next.js 16 (App Router — leer `node_modules/next/dist/docs/` antes de tocar routing/layout, ver `frontend/AGENTS.md`), TypeScript, Tailwind v4 (`--gob-navy`/`--gob-bone`/`--gob-ink`), framer-motion, @dnd-kit/core (^6.3.1), lucide-react.

**Nota de verificación:** El frontend NO tiene suite de pruebas unitarias de UI. La compuerta de cada tarea es: `npm run lint` (sin errores) + `npm run build` (type-check + build OK) + smoke manual descrito en cada tarea. Comandos desde `frontend/`.

---

### Task 1: `Sidebar` + `layout.tsx`

**Files:**
- Create: `frontend/src/components/ui/Sidebar.tsx`
- Modify: `frontend/src/app/dashboard/layout.tsx`
- Delete: `frontend/src/components/ui/TopNav.tsx`

- [ ] **Step 1: Crear `Sidebar.tsx`**

```tsx
"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import {
  Home, CalendarDays, ClipboardList, CheckSquare, Users,
  Settings, LogOut, Menu, X,
} from "lucide-react"
import { supabase } from "@/lib/supabase"
import { useOnboardingStore } from "@/lib/store"

const LINKS = [
  { href: "/dashboard", label: "Inicio", exact: true, icon: Home },
  { href: "/dashboard/sesion-del-mes", label: "Sesión del mes", exact: false, icon: CalendarDays },
  { href: "/dashboard/plan", label: "Plan", exact: false, icon: ClipboardList },
  { href: "/dashboard/compromisos", label: "Compromisos", exact: false, icon: CheckSquare },
  { href: "/dashboard/consejo", label: "Tu consejo", exact: false, icon: Users },
]

export default function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const { reset } = useOnboardingStore()
  const [open, setOpen] = useState(false)

  const signOut = async () => {
    await supabase.auth.signOut()
    reset()
    router.push("/")
  }

  const isActive = (href: string, exact: boolean) =>
    exact ? pathname === href : pathname.startsWith(href)

  const navBody = (
    <>
      <Link
        href="/dashboard"
        onClick={() => setOpen(false)}
        className="font-bold tracking-widest text-sm px-4 py-4 block"
      >
        GOBERNIA
      </Link>
      <nav className="flex-1 px-2 space-y-1">
        {LINKS.map(l => {
          const Icon = l.icon
          const active = isActive(l.href, l.exact)
          return (
            <Link
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors border-l-2 ${
                active
                  ? "bg-white/10 font-medium border-[var(--gob-bone)]"
                  : "opacity-70 hover:opacity-100 hover:bg-white/5 border-transparent"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {l.label}
            </Link>
          )
        })}
      </nav>
      <div className="border-t border-white/10 px-2 py-3 space-y-1">
        <Link
          href="/dashboard/datos"
          onClick={() => setOpen(false)}
          className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm opacity-70 hover:opacity-100 hover:bg-white/5"
        >
          <Settings className="h-4 w-4 shrink-0" /> Datos
        </Link>
        <button
          onClick={signOut}
          className="w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm opacity-70 hover:opacity-100 hover:bg-white/5"
        >
          <LogOut className="h-4 w-4 shrink-0" /> Salir
        </button>
      </div>
    </>
  )

  return (
    <>
      {/* Móvil: botón hamburguesa */}
      <button
        onClick={() => setOpen(true)}
        className="md:hidden fixed top-3 left-3 z-50 bg-[var(--gob-navy)] text-[var(--gob-bone)] rounded-lg p-2"
        aria-label="Abrir menú"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Móvil: overlay */}
      {open && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="relative w-60 h-dvh bg-[var(--gob-navy)] text-[var(--gob-bone)] flex flex-col">
            <button
              onClick={() => setOpen(false)}
              className="absolute top-3 right-3"
              aria-label="Cerrar menú"
            >
              <X className="h-5 w-5" />
            </button>
            {navBody}
          </aside>
        </div>
      )}

      {/* Escritorio: sidebar fijo */}
      <aside className="hidden md:flex fixed left-0 top-0 h-dvh w-60 bg-[var(--gob-navy)] text-[var(--gob-bone)] flex-col z-40">
        {navBody}
      </aside>
    </>
  )
}
```

- [ ] **Step 2: Reescribir `dashboard/layout.tsx`**

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

- [ ] **Step 3: Borrar `TopNav.tsx`**

```bash
git rm frontend/src/components/ui/TopNav.tsx
```

- [ ] **Step 4: Verificar que nada más importe `TopNav`**

Run: `grep -rn "TopNav" frontend/src`
Expected: sin resultados (solo el archivo borrado ya no aparece). Si aparece un import, eliminarlo.

- [ ] **Step 5: lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: ambos pasan sin errores.

- [ ] **Step 6: Smoke**

`npm run dev`, abrir el dashboard: el sidebar aparece a la izquierda en escritorio; los 5 ítems navegan; "Datos" y "Salir" funcionan; en móvil (ventana angosta) el botón hamburguesa abre/cierra el overlay. (Es esperado que los headers de algunas páginas se encimen todavía — se arregla en Task 2.)

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat(fase0): sidebar lateral reemplaza la TopNav"
```

---

### Task 2: Migración de headers de página (quitar compensación de la TopNav)

**Contexto:** Los headers de página usaban `fixed top-12 inset-x-0` para quedar **debajo** de la TopNav (`h-12` = 48px) y empujaban el contenido con `pt-26` (104px = 48 de TopNav + 56 del header). Sin TopNav: el header va a `top-0`, el contenido a `pt-14` (56px), y como el sidebar ocupa la izquierda en escritorio, los headers `fixed` (que ignoran el `md:ml-60` del layout) deben empezar después del sidebar con `md:left-60`.

**Files:**
- Modify: `frontend/src/app/dashboard/page.tsx`
- Modify: `frontend/src/app/dashboard/datos/page.tsx`
- Modify: `frontend/src/app/dashboard/sesion/[id]/page.tsx`

- [ ] **Step 1: `dashboard/page.tsx` — header (Inicio)**

En el `<header>` (actualmente línea ~212):
- Cambiar `fixed top-12 inset-x-0 z-30` → `fixed top-0 inset-x-0 md:left-60 z-30`.

En el `<main>` (actualmente línea ~389):
- Cambiar `pt-26` → `pt-14`.

(La limpieza de los enlaces "Mis datos"/"Salir" de este header se hace en Task 3, junto con la remoción de los consejeros. Aquí solo se ajusta el posicionamiento.)

- [ ] **Step 2: `dashboard/datos/page.tsx` — header**

En el `<header>` (actualmente línea ~73): `fixed top-12 inset-x-0 z-30` → `fixed top-0 inset-x-0 md:left-60 z-30`.
En el `<main>` (actualmente línea ~83): `pt-26` → `pt-14`.

- [ ] **Step 3: `dashboard/sesion/[id]/page.tsx` — headers**

Leer el archivo completo primero. Tiene dos barras fijas que compensaban la TopNav:
- `<header className="fixed top-12 inset-x-0 z-30 ...">` (~línea 235): `top-12` → `top-0`, añadir `md:left-60`.
- `<div className="fixed top-14 inset-x-0 z-40 ...">` (~línea 265): esta barra iba justo debajo del header; reducir su `top` en 48px (la altura de la TopNav eliminada) y añadir `md:left-60`. Si `top-14` representaba "TopNav(48) + 8px", queda `top-2`; verificar visualmente que las dos barras quedan apiladas sin encimarse ni dejar hueco, y ajustar el `padding-top` del contenido correspondiente en la misma proporción (restar 48px / `pt-12`).

Regla para este archivo: cualquier offset vertical que existía para dejar pasar la TopNav `h-12` se reduce en 48px (12 en escala Tailwind), y toda barra `fixed inset-x-0` recibe `md:left-60`.

- [ ] **Step 4: Verificar las demás páginas del dashboard**

Run: `grep -rn "top-12\|pt-26\|fixed top" frontend/src/app/dashboard/compromisos frontend/src/app/dashboard/sesion-del-mes frontend/src/app/dashboard/plan`
- Si aparece algún `top-12` / `pt-26` / header `fixed inset-x-0`, aplicar el mismo ajuste (`top-12`→`top-0`, `pt-26`→`pt-14`, añadir `md:left-60`).
- Si no aparece nada, estas páginas no dependían de la TopNav y no se tocan (heredan el `md:ml-60` del layout).

- [ ] **Step 5: lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: pasan sin errores.

- [ ] **Step 6: Smoke**

`npm run dev`: en Inicio, Datos y sesión/[id] el header queda pegado arriba (sin franja vacía de 48px), no se encima con el sidebar en escritorio, y el contenido no queda tapado por el header ni deja hueco. En móvil el header ocupa todo el ancho.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "fix(fase0): headers de página dejan de compensar la TopNav y respetan el sidebar"
```

---

### Task 3: Página "Tu consejo" + quitar consejeros de Inicio

**Files:**
- Create: `frontend/src/app/dashboard/consejo/page.tsx`
- Modify: `frontend/src/app/dashboard/page.tsx`

**Contexto:** En `dashboard/page.tsx` (Inicio) viven hoy: el array `AGENTS` (5 consejeros), la sección de tarjetas de consejeros (~líneas 585-628), el header propio con enlaces "Mis datos"/"Salir", dos modales (`showSetupModal` "Configura tu empresa" y `showModal` "Nueva sesión"), y el handler `tryCreateSession` que el botón de cada tarjeta dispara. La página "Tu consejo" necesita las tarjetas + ese flujo de "Iniciar sesión".

- [ ] **Step 1: Crear `dashboard/consejo/page.tsx`**

Página cliente que reproduce la sección de consejeros y el flujo "Iniciar sesión". Reusa el patrón de `dashboard/page.tsx`: resuelve la sesión de onboarding vía `api.get("/onboarding/my-session")` para saber si `onboardingComplete`, y al pulsar "Iniciar sesión" abre el modal de nueva sesión (si está completo) o el de setup (si no).

```tsx
"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import Link from "next/link"
import {
  ArrowRight, ArrowUpRight, Play, X, Loader2, Sparkles,
} from "lucide-react"
import { useOnboardingStore } from "@/lib/store"
import api from "@/lib/api"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

const AGENTS = [
  { tag: "Consejero en", name: "Finanzas",      desc: "Rentabilidad, flujo de caja y estructura de capital." },
  { tag: "Consejero en", name: "Estrategia",    desc: "Posicionamiento, mercado y crecimiento a largo plazo." },
  { tag: "Consejero en", name: "Riesgos",       desc: "Riesgos operativos, legales y planes de mitigación." },
  { tag: "Consejero en", name: "Auditoría",     desc: "Cumplimiento, control interno y Governance Score." },
  { tag: "Consejero",    name: "Independiente", desc: "El Retador: cuestiona cada decisión con un pre-mortem antes de actuar." },
]

const ETAPAS = [
  { n: 1, label: "Empresa" }, { n: 2, label: "Equipo" }, { n: 3, label: "Prioridades" },
  { n: 4, label: "Diagnóstico" }, { n: 5, label: "KPIs" }, { n: 6, label: "Gobierno" },
  { n: 7, label: "Documentos" }, { n: 8, label: "Visión" },
]

const MONTH_NAMES = [
  "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

interface BoardSession {
  board_session_id: string
  period_year: number
  period_month: number
}

export default function ConsejoPage() {
  const router = useRouter()
  const { sessionId, completedStages, hydrate, reset } = useOnboardingStore()

  const [sessions, setSessions] = useState<BoardSession[]>([])
  const [showSetupModal, setShowSetupModal] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [modalYear, setModalYear] = useState(new Date().getFullYear())
  const [modalMonth, setModalMonth] = useState(new Date().getMonth() + 1)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  useEffect(() => {
    api.get("/onboarding/my-session")
      .then(r => {
        const sid = r.data?.session_id
        if (sid) hydrate(sid, r.data.completed_stages ?? [])
        else reset()
      })
      .catch(() => {})
    api.get("/board-sessions").then(r => setSessions(r.data)).catch(() => {})
  }, [hydrate, reset])

  const onboardingComplete = completedStages.length >= 8
  const nextEtapa = ETAPAS.find(e => !completedStages.includes(e.n))
  const currentYear = new Date().getFullYear()
  const years = [currentYear - 1, currentYear, currentYear + 1]

  const openModal = () => {
    setModalYear(new Date().getFullYear())
    setModalMonth(new Date().getMonth() + 1)
    setCreateError(null)
    setShowModal(true)
  }

  const tryCreateSession = () => {
    if (onboardingComplete) openModal()
    else setShowSetupModal(true)
  }

  const createSession = async () => {
    setCreating(true)
    setCreateError(null)
    try {
      const r = await api.post("/board-sessions", { period_year: modalYear, period_month: modalMonth })
      setShowModal(false)
      router.push(`/dashboard/sesion/${r.data.board_session_id}`)
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status
      if (status === 409) {
        const existing = sessions.find(s => s.period_year === modalYear && s.period_month === modalMonth)
        if (existing) {
          setShowModal(false)
          router.push(`/dashboard/sesion/${existing.board_session_id}`)
          return
        }
      }
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setCreateError(msg ?? "No se pudo crear la sesión. Intenta de nuevo.")
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="min-h-dvh bg-white text-black antialiased">
      {/* Setup-required modal */}
      <AnimatePresence>
        {showSetupModal && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }} className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
              onClick={() => setShowSetupModal(false)} />
            <motion.div initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }} transition={{ duration: 0.25, ease: EASE }}
              className="fixed z-50 inset-x-4 top-1/2 -translate-y-1/2 max-w-sm mx-auto bg-white rounded-2xl shadow-xl p-8 space-y-5">
              <div className="w-12 h-12 rounded-full bg-gray-50 flex items-center justify-center">
                <Sparkles className="h-5 w-5 text-black" />
              </div>
              <div className="space-y-2">
                <h2 className="text-lg font-bold text-black">Configura tu empresa primero</h2>
                <p className="text-sm text-gray-500 leading-relaxed">
                  Para que el consejo de IA te entregue análisis útiles, necesitamos conocer tu empresa.
                  Toma unos minutos y solo se hace una vez.
                </p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => setShowSetupModal(false)}
                  className="flex-1 text-sm font-medium text-gray-500 hover:text-[var(--gob-navy)] transition-colors">
                  Más tarde
                </button>
                <Link href={nextEtapa ? `/onboarding/etapa-${nextEtapa.n}` : "/onboarding/etapa-1"}
                  className="flex-[2] inline-flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors">
                  {completedStages.length > 0 ? "Continuar configuración" : "Empezar"}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Nueva sesión modal */}
      <AnimatePresence>
        {showModal && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }} className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
              onClick={() => setShowModal(false)} />
            <motion.div initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }} transition={{ duration: 0.25, ease: EASE }}
              className="fixed z-50 inset-x-4 top-1/2 -translate-y-1/2 max-w-sm mx-auto bg-white rounded-2xl shadow-xl p-8 space-y-6">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-bold text-black">Nueva sesión de consejo</h2>
                  <p className="text-xs text-gray-400 mt-0.5">Selecciona el periodo a analizar</p>
                </div>
                <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-[var(--gob-navy)] transition-colors">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="space-y-2">
                <p className="text-xs font-medium text-gray-600">Mes</p>
                <div className="grid grid-cols-4 gap-1.5">
                  {MONTH_NAMES.slice(1).map((m, i) => (
                    <button key={i + 1} onClick={() => setModalMonth(i + 1)}
                      className={`py-2 rounded-lg text-xs font-medium border-2 transition-all duration-100 ${
                        modalMonth === i + 1
                          ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                          : "border-gray-100 text-gray-500 hover:border-gray-300"}`}>
                      {m.slice(0, 3)}
                    </button>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <p className="text-xs font-medium text-gray-600">Año</p>
                <div className="flex gap-2">
                  {years.map(y => (
                    <button key={y} onClick={() => setModalYear(y)}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium border-2 transition-all duration-100 ${
                        modalYear === y
                          ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                          : "border-gray-100 text-gray-500 hover:border-gray-300"}`}>
                      {y}
                    </button>
                  ))}
                </div>
              </div>
              {createError && <p className="text-xs text-red-500">{createError}</p>}
              <button onClick={createSession} disabled={creating}
                className="w-full flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-50">
                {creating
                  ? <><Loader2 className="h-4 w-4 animate-spin" /> Creando…</>
                  : <>Crear sesión de {MONTH_NAMES[modalMonth]} {modalYear} <ArrowRight className="h-4 w-4" /></>}
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <main className="pt-14">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)] py-12 space-y-8">
          <div className="space-y-1">
            <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Tu consejo</p>
            <h1 className="text-3xl font-bold text-black tracking-tight">Cinco consejeros con IA</h1>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {AGENTS.map((a, i) => (
              <motion.div key={a.name} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: EASE, delay: 0.05 + i * 0.07 }}
                className="group border border-gray-100 hover:border-gray-300 rounded-2xl p-6 space-y-4 transition-all duration-300 hover:shadow-sm flex flex-col">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs text-gray-400">{a.tag}</p>
                    <p className="text-base font-bold text-black mt-0.5">{a.name}</p>
                  </div>
                  <ArrowUpRight className={`h-4 w-4 mt-0.5 transition-colors ${
                    onboardingComplete ? "text-gray-200 group-hover:text-gray-400" : "text-gray-100"}`} />
                </div>
                <p className="text-xs text-gray-500 leading-relaxed flex-1">{a.desc}</p>
                <button onClick={tryCreateSession}
                  className="w-full flex items-center justify-between text-xs font-medium py-2.5 px-3 rounded-xl border border-gray-200 text-gray-700 hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] transition-all duration-150">
                  Iniciar sesión
                  <Play className="h-3 w-3" />
                </button>
              </motion.div>
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}
```

Nota: el `sessionId` del store se desestructura para mantener el patrón pero no se usa directamente aquí; si `npm run lint` lo marca como no usado, quitarlo de la desestructuración (`const { completedStages, hydrate, reset } = useOnboardingStore()`).

- [ ] **Step 2: Quitar la sección de consejeros de `dashboard/page.tsx`**

- Eliminar el bloque JSX de la sección "Agents" (el `<motion.div>` que contiene "Tu consejo" / "Cinco consejeros con IA" y el `grid` con `AGENTS.map`, ~líneas 585-628).
- Eliminar la constante `AGENTS` (~líneas 22-28) si ya no se usa.
- En el `<header>` de esta página, eliminar el enlace "Mis datos" (`<Link href="/dashboard/datos">…`) y el botón "Salir" (`handleSignOut`), porque ahora viven en el sidebar. Si tras quitarlos el `<header>` queda solo con el logo y no aporta, puede dejarse solo el logo o eliminarse el `<header>` (y su `pt-14` asociado). Mantener el `userEmail` si se desea, o quitarlo con el resto.
- Si `handleSignOut`, `LogOut`, `Settings`, o `AGENTS` quedan sin uso tras lo anterior, eliminarlos. `npm run lint` los señalará.

- [ ] **Step 3: lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: pasan sin errores (sin variables/imports sin usar).

- [ ] **Step 4: Smoke**

`npm run dev`: la página `/dashboard/consejo` muestra las 5 tarjetas; "Iniciar sesión" abre el modal de nueva sesión (onboarding completo) o el de setup (incompleto). La página Inicio ya NO muestra los consejeros y su header ya no tiene "Mis datos"/"Salir". El ítem "Tu consejo" del sidebar queda activo en esta ruta.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(fase0): página 'Tu consejo' con los 5 consejeros; Inicio queda más limpio"
```

---

### Task 4: Componente `MonthKanban`

**Files:**
- Create: `frontend/src/components/plan/MonthKanban.tsx`

**Contexto:** Adaptado de `AcuerdosBoard.tsx` (recuperable con `git show 9067d8e^:frontend/src/components/plan/AcuerdosBoard.tsx`). Diferencia clave: el original recibía el `AnnualPlan` completo y aplanaba tareas de los 12 meses (con etiqueta de mes por tarjeta). `MonthKanban` recibe los **objetivos de un solo mes**, aplana sus tareas, y no muestra etiqueta de mes. Al soltar en otra columna llama `onUpdateTask(id, { status })` (en vez del antiguo `onMoveTask`). Conserva el gate: no se puede mover a "Validado" (`completada`) una tarea con `evidence_count === 0`.

- [ ] **Step 1: Crear `MonthKanban.tsx`**

```tsx
"use client"

import { useState } from "react"
import {
  DndContext, PointerSensor, useSensor, useSensors,
  useDraggable, useDroppable, type DragEndEvent,
} from "@dnd-kit/core"
import { Paperclip } from "lucide-react"
import { Objective, Task } from "@/lib/annualPlan"

const COLUMNS: { id: Task["status"]; label: string }[] = [
  { id: "pendiente", label: "Pendiente" },
  { id: "en_progreso", label: "En proceso" },
  { id: "completada", label: "Validado" },
]
const PRIO_DOT: Record<string, string> = { alta: "bg-red-400", media: "bg-amber-400", baja: "bg-gray-300" }

function Card({ task, onClick }: { task: Task; onClick: () => void }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: task.id })
  const style = transform
    ? { transform: `translate(${transform.x}px, ${transform.y}px)`, zIndex: 50 }
    : undefined
  return (
    <div
      ref={setNodeRef} style={style} {...attributes} {...listeners}
      onClick={onClick}
      className={`bg-white border border-gray-100 rounded-xl p-3 space-y-2 cursor-grab active:cursor-grabbing ${isDragging ? "opacity-50" : ""}`}
    >
      <p className="text-sm text-black font-medium leading-snug">{task.title}</p>
      <div className="flex items-center gap-2 text-[11px] text-gray-400">
        <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${PRIO_DOT[task.priority] ?? "bg-gray-300"}`} />
        {task.owner && <span className="truncate">{task.owner}</span>}
        {task.evidence_count > 0 && (
          <span className="ml-auto inline-flex items-center gap-0.5 text-gray-500">
            <Paperclip className="h-3 w-3" />{task.evidence_count}
          </span>
        )}
      </div>
    </div>
  )
}

function Column({
  id, label, tasks, onTaskClick,
}: { id: Task["status"]; label: string; tasks: Task[]; onTaskClick: (t: Task) => void }) {
  const { setNodeRef, isOver } = useDroppable({ id })
  return (
    <div ref={setNodeRef} className={`flex-1 min-w-0 rounded-2xl p-3 space-y-2 transition-colors ${isOver ? "bg-gray-100" : "bg-gray-50/60"}`}>
      <div className="flex items-center justify-between px-1">
        <span className="text-xs font-bold text-gray-500 uppercase tracking-wide">{label}</span>
        <span className="text-xs text-gray-400">{tasks.length}</span>
      </div>
      {tasks.map(t => (
        <Card key={t.id} task={t} onClick={() => onTaskClick(t)} />
      ))}
      {tasks.length === 0 && <p className="text-xs text-gray-300 px-1 py-6 text-center">—</p>}
    </div>
  )
}

export default function MonthKanban({
  objectives, onTaskClick, onUpdateTask,
}: {
  objectives: Objective[]
  onTaskClick: (task: Task) => void
  onUpdateTask: (taskId: string, patch: Partial<Task>) => void
}) {
  const [warn, setWarn] = useState<string | null>(null)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  const tasks: Task[] = objectives.flatMap(o => o.tasks)

  const onDragEnd = (e: DragEndEvent) => {
    const id = String(e.active.id)
    const over = e.over ? String(e.over.id) : null
    if (!over) return
    const task = tasks.find(t => t.id === id)
    if (!task) return
    if (!COLUMNS.some(c => c.id === over)) return
    if (over === task.status) return
    if (over === "completada" && task.evidence_count === 0) {
      setWarn("Sube evidencia para validar esta tarea (abre la tarjeta).")
      return
    }
    setWarn(null)
    onUpdateTask(id, { status: over as Task["status"] })
  }

  return (
    <div className="space-y-3">
      {warn && <p className="text-xs text-red-500">{warn}</p>}
      <DndContext sensors={sensors} onDragEnd={onDragEnd}>
        <div className="flex gap-3 items-start">
          {COLUMNS.map(c => (
            <Column
              key={c.id} id={c.id} label={c.label}
              tasks={tasks.filter(t => t.status === c.id)}
              onTaskClick={onTaskClick}
            />
          ))}
        </div>
      </DndContext>
    </div>
  )
}
```

- [ ] **Step 2: lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: pasan. (El componente aún no se usa; un export por defecto sin importar no rompe el build.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/plan/MonthKanban.tsx && git commit -m "feat(fase0): MonthKanban — tablero arrastrable acotado a un mes"
```

---

### Task 5: Rewire `MonthDetail` (kanban + orden del día) y limpiar `plan/page.tsx`

**Files:**
- Modify: `frontend/src/components/plan/MonthDetail.tsx`
- Modify: `frontend/src/app/dashboard/plan/page.tsx`

**Contexto:** `MonthDetail` pasa de usar `TasksTable` (agrupada por objetivo, con renombrar/borrar objetivo, agregar tarea, agregar objetivo) a `MonthKanban` (agrupado por estado). En consecuencia se eliminan de la vista del mes esas acciones por-objetivo y el botón "Agregar objetivo"; editar/borrar una tarea sigue disponible al abrir su tarjeta (el `TaskDrawer` que ya existe en `plan/page.tsx`). El orden del día se mueve a una sección legible, expandida por defecto, debajo del kanban.

- [ ] **Step 1: Reescribir `MonthDetail.tsx`**

```tsx
"use client"

import { useMemo, useState } from "react"
import { motion } from "framer-motion"
import { CheckCircle2, ChevronDown } from "lucide-react"
import type { MonthlyPlan, Task, MonthReview } from "@/lib/annualPlan"
import { MONTH_NAMES } from "@/lib/annualPlan"
import MonthReviewPanel from "./MonthReviewPanel"
import MonthKanban from "./MonthKanban"
import OrdenDelDiaPanel from "@/components/plan/OrdenDelDiaPanel"

export default function MonthDetail({
  month, onTaskClick, onUpdateTask, onCloseMonth, onApplyProposal,
}: {
  month: MonthlyPlan
  onTaskClick: (t: Task) => void
  onUpdateTask: (taskId: string, patch: Partial<Task>) => void
  onCloseMonth: (monthlyPlanId: string) => void
  onApplyProposal: (monthIndex: number, proposalId: string) => void
}) {
  const [ordenOpen, setOrdenOpen] = useState(true)

  const kpis = useMemo(
    () => Array.from(new Set(month.objectives.flatMap(o => o.kpi_refs))).slice(0, 6),
    [month.objectives],
  )

  return (
    <motion.div
      key={month.id}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-5"
    >
      <div>
        <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">
          {MONTH_NAMES[month.period_month]} {month.period_year} · Mes {month.month_index}
        </p>
        {month.focus && <h2 className="text-xl font-bold text-black mt-1">{month.focus}</h2>}
      </div>

      {kpis.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] uppercase tracking-wide text-gray-400 font-medium">KPIs:</span>
          {kpis.map(k => (
            <span key={k} className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
              {k}
            </span>
          ))}
        </div>
      )}

      {month.status === "done" && month.review && (
        <MonthReviewPanel
          review={month.review as unknown as MonthReview}
          onApply={pid => onApplyProposal(month.month_index, pid)}
        />
      )}

      <MonthKanban
        objectives={month.objectives}
        onTaskClick={onTaskClick}
        onUpdateTask={onUpdateTask}
      />

      {/* Orden del día — legible, expandido por defecto, debajo de las tareas */}
      <section className="border border-gray-100 rounded-2xl overflow-hidden">
        <button
          type="button"
          onClick={() => setOrdenOpen(v => !v)}
          className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50"
        >
          <span className="text-sm font-bold text-black">Orden del día</span>
          <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${ordenOpen ? "rotate-180" : ""}`} />
        </button>
        {ordenOpen && (
          <div className="px-4 pb-4 border-t border-gray-100 pt-3">
            <OrdenDelDiaPanel monthIndex={month.month_index} />
          </div>
        )}
      </section>

      {month.status === "active" && (
        <button
          onClick={() => onCloseMonth(month.id)}
          className="w-full flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium rounded-xl py-3 hover:bg-[var(--gob-ink)] transition-colors"
        >
          <CheckCircle2 className="h-4 w-4" /> Cerrar mes y revisar
        </button>
      )}
    </motion.div>
  )
}
```

- [ ] **Step 2: Actualizar la llamada a `MonthDetail` en `plan/page.tsx`**

Reemplazar el bloque (~líneas 280-292):

```tsx
          {month && (
            <MonthDetail
              month={month}
              onTaskClick={setOpenTask}
              onUpdateTask={onUpdateTask}
              onCloseMonth={onCloseMonth}
              onApplyProposal={onApplyProposal}
            />
          )}
```

- [ ] **Step 3: Eliminar handlers sin uso en `plan/page.tsx`**

Eliminar las funciones completas:
- `onAddTask` (~líneas 133-144)
- `onRenameObjective` (~líneas 146-153)
- `onDeleteObjective` (~líneas 155-160)
- `onAddObjective` (~líneas 162-169)

NO eliminar `onUpdateTask`, `onDeleteTask`, `patchTaskLocal`, `onCloseMonth`, `onSubmitClose`, `onApplyProposal` (siguen en uso).

- [ ] **Step 4: Eliminar imports que quedaron sin uso**

Tras quitar los handlers, estos imports de `@/lib/annualPlan` quedan sin uso: `createTask`, `createObjective`, `updateObjective`, `deleteObjective`. Eliminarlos del bloque de import (conservar `updateTask` y `deleteTask`, que siguen usándose).

Run: `cd frontend && npm run lint`
Expected: lint señala exactamente los imports/variables sin usar si quedó alguno; eliminarlos hasta que pase limpio. No debe quedar referencia a `TasksTable` ni a los handlers borrados.

- [ ] **Step 5: build**

Run: `cd frontend && npm run build`
Expected: pasa sin errores de tipos (la nueva firma de `MonthDetail` no recibe los props eliminados).

- [ ] **Step 6: Smoke**

`npm run dev`, ir a `/dashboard/plan` con un plan activo:
- La vista del mes muestra el **kanban de 3 columnas** (Pendiente · En proceso · Validado) en vez de la tabla.
- Arrastrar una tarjeta a otra columna cambia su estado (persistente al recargar).
- Arrastrar a "Validado" una tarjeta sin evidencia muestra el aviso y NO la mueve.
- Clic en una tarjeta abre el detalle (editar/borrar siguen funcionando).
- NO aparece el botón "Agregar objetivo".
- Debajo del kanban aparece la sección **"Orden del día"** expandida por defecto, colapsable.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat(fase0): kanban reemplaza la tabla en la vista del mes; orden del día legible; sin 'agregar objetivo'"
```

---

## Self-Review (cobertura del spec)

- **Componente 1 (Sidebar)** → Task 1. ✅
- **Componente 2 (layout)** → Task 1. ✅
- **Componente 3 (migración de headers)** → Task 2. ✅
- **Componente 4 (Tu consejo + limpieza Inicio)** → Task 3. ✅
- **Componente 5 (kanban reemplaza tabla)** → Task 4 (componente) + Task 5 (integración). ✅
- **Componente 6 (quitar Agregar objetivo)** → Task 5. ✅
- **Componente 7 (orden del día debajo)** → Task 5. ✅

Consistencia de tipos: `MonthKanban` usa `Objective`/`Task` de `@/lib/annualPlan`; su prop `onUpdateTask(taskId, patch)` coincide con el handler existente `onUpdateTask` de `plan/page.tsx`. La nueva firma de `MonthDetail` (sin `onAddTask`/`onAddObjective`/`onRenameObjective`/`onDeleteObjective`) coincide con la llamada actualizada en Task 5 Step 2.

Orden de ejecución: 1 → 2 → 3 → 4 → 5. Task 4 es independiente y podría ir antes; Task 5 depende de Task 4.
