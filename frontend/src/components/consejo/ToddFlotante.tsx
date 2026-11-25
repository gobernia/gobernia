"use client"

// Botón flotante de Todd — presente en TODO el dashboard (se monta en el
// layout). Abre el panel del Secretario desde cualquier página.
//   · Cualquier botón de la app puede abrirlo disparando el evento
//     window "todd:abrir" (así las páginas no duplican su propio cajón).
//   · Cuando Todd cambia una tarea, se emite "todd:tarea-cambiada" para que
//     el tablero (si está visible) se refresque.
//   · "todd:aviso" muestra un globo junto al botón: Todd "vigila" los documentos
//     que se suben y avisa en cuanto el Auditor los revisó (ver lib/toddEventos).

import { useEffect, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Loader2, MessageSquare, X } from "lucide-react"
import ToddSecretario from "@/components/consejo/ToddSecretario"
import type { ToddAviso } from "@/lib/toddEventos"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

const CARD  = "#FFFFFF"
const MUTED = "#6E7686"
const ACCENT = "#C2410C"
const LINE  = "#E2E2DC"

export default function ToddFlotante() {
  const [open, setOpen] = useState(false)
  const [aviso, setAviso] = useState<ToddAviso | null>(null)

  useEffect(() => {
    const abrir = () => { setAviso(null); setOpen(true) }
    const cerrar = () => setOpen(false)
    const avisar = (e: Event) => setAviso((e as CustomEvent<ToddAviso>).detail ?? null)
    window.addEventListener("todd:abrir", abrir)
    window.addEventListener("todd:cerrar", cerrar)
    window.addEventListener("todd:aviso", avisar)
    return () => {
      window.removeEventListener("todd:abrir", abrir)
      window.removeEventListener("todd:cerrar", cerrar)
      window.removeEventListener("todd:aviso", avisar)
    }
  }, [])

  // Con el panel abierto el globo sobra: el mensaje ya está en el chat.
  const globo = open ? null : aviso
  const abrirDesdeGlobo = () => { setAviso(null); setOpen(true) }

  return (
    <>
      {/* Globo de Todd: avisa que está leyendo un documento y, al terminar, qué encontró */}
      <AnimatePresence>
        {globo && (
          <motion.div
            key={globo.texto}
            initial={{ opacity: 0, y: 8, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8 }} transition={{ duration: 0.2, ease: EASE }}
            role="status" aria-live="polite"
            className="fixed z-40 flex items-start gap-2 rounded-2xl p-3 pr-2 shadow-lg"
            style={{
              right: "calc(1.5rem + env(safe-area-inset-right, 0px))",
              bottom: "calc(6rem + env(safe-area-inset-bottom, 0px))",
              width: "min(300px, calc(100vw - 3rem))",
              background: CARD, border: `1px solid ${LINE}`,
            }}
          >
            <button type="button" onClick={abrirDesdeGlobo} disabled={globo.leyendo}
              className="flex flex-1 items-start gap-2 text-left min-w-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 disabled:cursor-default"
              style={{ outlineColor: ACCENT }}>
              <span className="h-7 w-7 shrink-0 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-bold flex items-center justify-center">
                T
              </span>
              <span className="min-w-0 space-y-1">
                <span className="block text-[13px] leading-snug text-[var(--gob-ink)]">{globo.texto}</span>
                {globo.leyendo ? (
                  <span className="inline-flex items-center gap-1 text-[11px]" style={{ color: MUTED }}>
                    <Loader2 className="h-3 w-3 animate-spin" /> El Auditor lo está revisando
                  </span>
                ) : (
                  <span className="block text-[11px] font-semibold" style={{ color: ACCENT }}>Ver lo que dice Todd</span>
                )}
              </span>
            </button>
            <button type="button" onClick={() => setAviso(null)} aria-label="Cerrar el aviso de Todd"
              className="shrink-0 inline-flex h-6 w-6 items-center justify-center rounded-md transition-colors hover:bg-[#E8E3D8]"
              style={{ color: MUTED }}>
              <X className="h-3.5 w-3.5" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* FAB — siempre visible, abajo a la derecha */}
      <button
        type="button"
        onClick={abrirDesdeGlobo}
        aria-label="Pregúntale a Todd, el Secretario del Consejo"
        title="Pregúntale a Todd"
        className="fixed bottom-6 right-6 z-40 grid h-14 w-14 place-items-center rounded-full text-white shadow-lg transition-all hover:scale-105 hover:brightness-95"
        style={{ background: ACCENT, boxShadow: "0 10px 28px -8px rgba(194,65,12,.55)" }}
      >
        <MessageSquare className="h-6 w-6" />
        {globo && !globo.leyendo && (
          <span aria-hidden className="absolute top-0.5 right-0.5 h-3.5 w-3.5 rounded-full border-2 border-white bg-[var(--gob-navy)]" />
        )}
      </button>

      {/* Cajón lateral del Secretario */}
      <AnimatePresence>
        {open && (
          <>
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }} className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm"
              onClick={() => setOpen(false)}
            />
            <motion.div
              initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }}
              transition={{ duration: 0.3, ease: EASE }}
              className="fixed right-0 top-0 z-50 flex h-dvh w-full max-w-[400px] flex-col shadow-2xl"
              style={{ background: CARD, borderLeft: `1px solid ${LINE}` }}
            >
              <button
                onClick={() => setOpen(false)}
                aria-label="Cerrar el panel de Todd"
                className="absolute top-3 right-3 z-10 inline-flex h-8 w-8 items-center justify-center rounded-[10px] transition-colors hover:bg-[#E8E3D8]"
                style={{ color: MUTED }}
              >
                <X className="h-4 w-4" />
              </button>
              <ToddSecretario
                fill
                onTareaCambiada={() => window.dispatchEvent(new Event("todd:tarea-cambiada"))}
              />
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
