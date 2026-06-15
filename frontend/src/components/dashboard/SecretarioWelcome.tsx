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
    if (!seen) localStorage.setItem(seenKey(userKey), "1")
    // Defer state updates out of the synchronous effect body
    queueMicrotask(() => {
      setMode(seen ? "reminder" : "full")
      setOpen(true)
    })
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
