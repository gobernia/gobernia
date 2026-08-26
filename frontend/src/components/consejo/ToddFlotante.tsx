"use client"

// Botón flotante de Todd — presente en TODO el dashboard (se monta en el
// layout). Abre el panel del Secretario desde cualquier página.
//   · Cualquier botón de la app puede abrirlo disparando el evento
//     window "todd:abrir" (así las páginas no duplican su propio cajón).
//   · Cuando Todd cambia una tarea, se emite "todd:tarea-cambiada" para que
//     el tablero (si está visible) se refresque.

import { useEffect, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { MessageSquare, X } from "lucide-react"
import ToddSecretario from "@/components/consejo/ToddSecretario"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

const CARD  = "#FFFFFF"
const MUTED = "#6E7686"
const ACCENT = "#C2410C"
const LINE  = "#E2E2DC"

export default function ToddFlotante() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const abrir = () => setOpen(true)
    window.addEventListener("todd:abrir", abrir)
    return () => window.removeEventListener("todd:abrir", abrir)
  }, [])

  return (
    <>
      {/* FAB — siempre visible, abajo a la derecha */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Pregúntale a Todd, el Secretario del Consejo"
        title="Pregúntale a Todd"
        className="fixed bottom-6 right-6 z-40 grid h-14 w-14 place-items-center rounded-full text-white shadow-lg transition-all hover:scale-105 hover:brightness-95"
        style={{ background: ACCENT, boxShadow: "0 10px 28px -8px rgba(194,65,12,.55)" }}
      >
        <MessageSquare className="h-6 w-6" />
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
