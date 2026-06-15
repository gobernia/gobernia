# Fase 1 — Modal de bienvenida del Secretario — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un modal de bienvenida del "Secretario del Consejo" en el Inicio del dashboard que guía a completar el onboarding, con modo completo la primera vez y recordatorio corto después, solo en frontend.

**Architecture:** Componente cliente `SecretarioWelcome.tsx` montado en `dashboard/page.tsx`. Decide en un `useEffect` si mostrarse (onboarding incompleto + no cerrado esta sesión) y en qué modo (completo si no ha visto la versión larga según `localStorage` por usuario; recordatorio si ya la vio). Sin backend.

**Tech Stack:** Next.js 16 App Router (client component — ver `frontend/AGENTS.md`), TypeScript, framer-motion, lucide-react, Tailwind v4 (`--gob-navy`/`--gob-bone`/`--gob-ink`).

**Nota de verificación:** El frontend no tiene suite de pruebas de UI. La compuerta es `npm run lint` + `npm run build` (sin errores nuevos) + smoke manual. Comandos desde `frontend/`. Errores de lint preexistentes en `datos/page.tsx`, `sesion/[id]/plan/page.tsx`, `onboarding/` están fuera de alcance.

---

### Task 1: Componente `SecretarioWelcome` + montaje en el Inicio

**Files:**
- Create: `frontend/src/components/dashboard/SecretarioWelcome.tsx`
- Modify: `frontend/src/app/dashboard/page.tsx`

- [ ] **Step 1: Crear `SecretarioWelcome.tsx`**

Crear el archivo con EXACTAMENTE este contenido:

```tsx
"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import { ArrowRight, Sparkles, X } from "lucide-react"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

const SESSION_KEY = "gobernia_secretario_welcome_dismissed"
const seenKey = (userKey: string) => `gobernia_secretario_welcome_seen_${userKey}`

export default function SecretarioWelcome({
  onboardingComplete, nextStageHref, userKey,
}: {
  onboardingComplete: boolean
  nextStageHref: string
  userKey: string
}) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<"full" | "reminder">("full")
  const ran = useRef(false)

  useEffect(() => {
    if (ran.current) return
    if (typeof window === "undefined") return
    if (onboardingComplete || !userKey) return // espera a que cargue el usuario; si está completo, nunca se muestra
    ran.current = true

    if (sessionStorage.getItem(SESSION_KEY) === "1") return // cerrado en esta sesión

    const seen = localStorage.getItem(seenKey(userKey)) === "1"
    if (seen) {
      setMode("reminder")
    } else {
      setMode("full")
      localStorage.setItem(seenKey(userKey), "1")
    }
    setOpen(true)
  }, [onboardingComplete, userKey])

  const dismiss = () => {
    if (typeof window !== "undefined") sessionStorage.setItem(SESSION_KEY, "1")
    setOpen(false)
  }

  const isFull = mode === "full"

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
            onClick={dismiss}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }} transition={{ duration: 0.25, ease: EASE }}
            className="fixed z-50 inset-x-4 top-1/2 -translate-y-1/2 max-w-sm mx-auto bg-white rounded-2xl shadow-xl p-8 space-y-5"
          >
            <button
              onClick={dismiss}
              aria-label="Cerrar"
              className="absolute top-4 right-4 text-gray-300 hover:text-[var(--gob-navy)] transition-colors"
            >
              <X className="h-4 w-4" />
            </button>

            <div className="w-12 h-12 rounded-full bg-gray-50 flex items-center justify-center">
              <Sparkles className="h-5 w-5 text-black" />
            </div>

            <div className="space-y-2">
              <h2 className="text-lg font-bold text-black">
                {isFull ? "Soy el Secretario de tu consejo" : "Aún falta completar tus datos"}
              </h2>
              <p className="text-sm text-gray-500 leading-relaxed">
                {isFull
                  ? "Para que tus consejeros trabajen con tu empresa, necesito que completes tu información: empresa, equipo, prioridades, KPIs y gobierno. Toma unos minutos y se hace una sola vez."
                  : "Para activar tu consejo necesito que termines tu información. Continúa donde lo dejaste."}
              </p>
            </div>

            <div className="flex gap-2">
              <button
                onClick={dismiss}
                className="flex-1 text-sm font-medium text-gray-500 hover:text-[var(--gob-navy)] transition-colors"
              >
                Más tarde
              </button>
              <Link
                href={nextStageHref}
                onClick={() => setOpen(false)}
                className="flex-[2] inline-flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors"
              >
                {isFull ? "Empezar" : "Continuar"}
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
```

Notas de diseño (para el implementador):
- El `ran` ref garantiza que la decisión se tome **una sola vez** (evita que React Strict Mode en dev voltee el modo a "reminder" por el doble-invoke del efecto, ya que marcar `localStorage` al mostrar el modo completo haría que la segunda corrida lo lea como visto).
- Marcar `localStorage` ocurre al **mostrar** el modo completo, así que aunque el usuario cierre con "Más tarde", la próxima sesión verá el recordatorio.
- "Empezar"/"Continuar" navega y cierra (sin marcar `sessionStorage`, no hace falta: navega fuera del dashboard).

- [ ] **Step 2: Montar el componente en `dashboard/page.tsx`**

En `frontend/src/app/dashboard/page.tsx`:

1. Agregar el import (junto a los demás imports de componentes, p. ej. cerca de `import GoberniaLogo from "@/components/ui/GoberniaLogo"`):

```tsx
import SecretarioWelcome from "@/components/dashboard/SecretarioWelcome"
```

2. Dentro del `return`, inmediatamente después de la etiqueta de apertura del `<div className="min-h-dvh bg-white text-black font-sans antialiased">` (el contenedor raíz de la página), montar el componente:

```tsx
      <SecretarioWelcome
        onboardingComplete={onboardingComplete}
        nextStageHref={nextEtapa ? `/onboarding/etapa-${nextEtapa.n}` : "/onboarding/etapa-1"}
        userKey={userEmail ?? ""}
      />
```

`onboardingComplete`, `nextEtapa` y `userEmail` ya existen en el componente `DashboardPage` (no redefinir). El modal es `fixed`, así que su posición en el árbol no afecta el layout.

- [ ] **Step 3: lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: ambos pasan sin errores nuevos. `SecretarioWelcome.tsx` y `dashboard/page.tsx` sin warnings de variables/imports sin usar introducidos por este cambio.

- [ ] **Step 4: Smoke manual (describir, no ejecutar navegador)**

No hay navegador disponible para el subagente; basta con que `build` pase. Para referencia del verificador humano:
- Usuario con onboarding **incompleto** (cuenta nueva de `/sign-up`): primera carga → modo completo; recarga → recordatorio; "Más tarde" → cierra y no reaparece en la sesión.
- Usuario con onboarding **completo** (djbeuvrin) → no aparece.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(fase1): modal de bienvenida del Secretario (completo + recordatorio)"
```

---

## Self-Review (cobertura del spec)

- **Componente `SecretarioWelcome` con props `onboardingComplete`/`nextStageHref`/`userKey`** → Task 1 Step 1. ✅
- **Lógica de visibilidad (onboarding incompleto, sessionStorage, localStorage por usuario, modo completo vs recordatorio, marcar al mostrar)** → Task 1 Step 1 (`useEffect` + `ran` ref). ✅
- **Contenido modo completo y recordatorio (copia aprobada)** → Task 1 Step 1 (ternarios `isFull`). ✅
- **Botones "Empezar"/"Continuar" (Link a `nextStageHref`) y "Más tarde"/backdrop/X (cierra + marca sesión)** → Task 1 Step 1. ✅
- **Estilo reusando el patrón de modales del dashboard** → Task 1 Step 1 (mismas clases/EASE). ✅
- **Montaje en `dashboard/page.tsx` con los props reusando estado existente** → Task 1 Step 2. ✅
- **No se toca banner ni modal de setup ni backend** → el plan no los modifica. ✅

Consistencia: el componente solo depende de `onboardingComplete: boolean`, `nextStageHref: string`, `userKey: string` — los tres existen en `DashboardPage` (`onboardingComplete`, `nextEtapa`, `userEmail`). Sin placeholders.
