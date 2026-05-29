"use client"

import { useState, useRef, useEffect, useId } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Info } from "lucide-react"

/**
 * Ícono (i) con tooltip de ayuda. En escritorio aparece al pasar el mouse
 * (o con foco de teclado); en táctil se abre al tocar y se cierra al tocar
 * fuera o con Escape. Sin librerías externas.
 */
export default function InfoHint({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)
  const id = useId()

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onDoc)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDoc)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  return (
    <span ref={ref} className="relative inline-flex align-middle">
      <button
        type="button"
        aria-label="Más información"
        aria-describedby={open ? id : undefined}
        onClick={() => setOpen(o => !o)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="text-gray-300 hover:text-[var(--gob-navy)] transition-colors focus:outline-none focus:text-[var(--gob-navy)]"
      >
        <Info className="h-3.5 w-3.5" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.span
            id={id}
            role="tooltip"
            initial={{ opacity: 0, y: 4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="absolute bottom-full left-1/2 z-50 mb-2 w-60 max-w-[60vw] -translate-x-1/2 rounded-xl border border-gray-200 bg-white px-3 py-2 text-[11px] font-normal normal-case leading-relaxed tracking-normal text-gray-600 shadow-lg pointer-events-none"
          >
            {text}
          </motion.span>
        )}
      </AnimatePresence>
    </span>
  )
}
