"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"

const STORAGE_KEY = "gobernia-cookie-consent"

/**
 * Banner discreto de aceptación de cookies — slide up desde abajo en el primer load.
 * Mantiene el estilo de la landing (Gabriel Sans, navy + bone, line-divider).
 * Persiste la decisión del usuario en localStorage.
 */
export default function CookieBanner() {
  const [show, setShow] = useState(false)

  useEffect(() => {
    const consent = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null
    if (!consent) {
      // Pequeño delay para que aparezca después del fade-in del hero
      const t = setTimeout(() => setShow(true), 1500)
      return () => clearTimeout(t)
    }
  }, [])

  const handle = (value: "accepted" | "rejected") => {
    try {
      localStorage.setItem(STORAGE_KEY, value)
    } catch {}
    setShow(false)
  }

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ y: "100%" }}
          animate={{ y: 0 }}
          exit={{ y: "100%" }}
          transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
          className="fixed bottom-0 inset-x-0 z-50 bg-white border-t border-[var(--gob-rule)]"
          style={{ fontFamily: "var(--font-sans)" }}
          role="dialog"
          aria-label="Aceptación de cookies"
        >
          <div className="max-w-[1400px] mx-auto px-6 sm:px-12 lg:px-20 py-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between sm:gap-8">
            <p
              className="text-sm text-[var(--gob-muted)] leading-relaxed flex-1"
              style={{ fontWeight: 300, maxWidth: 720 }}
            >
              Usamos cookies para mejorar tu experiencia y entender cómo se usa la plataforma.
              Puedes aceptarlas o rechazarlas en cualquier momento.
            </p>
            <div className="flex items-center gap-3 flex-shrink-0">
              <button
                type="button"
                onClick={() => handle("rejected")}
                className="inline-flex items-center gap-1.5 text-sm font-medium border border-[var(--gob-navy)] text-[var(--gob-navy)] bg-white px-4 py-2 rounded-lg hover:bg-[var(--gob-bone)] transition-colors"
              >
                Rechazar
              </button>
              <button
                type="button"
                onClick={() => handle("accepted")}
                className="inline-flex items-center gap-1.5 text-sm font-medium bg-[var(--gob-navy)] text-[var(--gob-bone)] px-4 py-2 rounded-lg hover:bg-[var(--gob-ink)] transition-colors"
              >
                Aceptar
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
