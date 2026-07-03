"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import {
  HelpCircle, X, ArrowRight, MessagesSquare, FileSearch, LayoutGrid, ClipboardList,
} from "lucide-react"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]
const SEEN_KEY = "gobernia_tour_v1"

const STEPS = [
  { icon: MessagesSquare, title: "Todd te entrevista", desc: "Responde unas preguntas sobre tu empresa. Todd arma tu perfil, sin formularios largos." },
  { icon: FileSearch, title: "Recibes tu diagnóstico", desc: "Tu consejo con IA analiza tu empresa —incluida investigación web— y te entrega un diagnóstico con fuentes." },
  { icon: LayoutGrid, title: "Se arma tu matriz FODA", desc: "Cruzamos lo interno con el entorno y tus prioridades para construir tu FODA." },
  { icon: ClipboardList, title: "Obtienes tu plan a 3 años", desc: "Un plan mes a mes con tareas explicadas. ¿Una no te encaja? La IA te propone una alternativa." },
]

export default function WelcomeTour() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (!localStorage.getItem(SEEN_KEY)) setOpen(true)
    } catch { /* SSR / storage bloqueado */ }
  }, [])

  const close = () => {
    setOpen(false)
    try { localStorage.setItem(SEEN_KEY, "1") } catch { /* noop */ }
  }

  return (
    <>
      {/* Botón de ayuda flotante */}
      <button
        onClick={() => setOpen(true)}
        aria-label="¿Cómo funciona Gobernia?"
        className="fixed bottom-5 right-5 z-40 w-11 h-11 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] shadow-lg flex items-center justify-center hover:bg-[var(--gob-ink)] transition-colors"
      >
        <HelpCircle className="h-5 w-5" />
      </button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm"
              onClick={close}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 20 }} transition={{ duration: 0.25, ease: EASE }}
              className="fixed z-50 inset-x-4 top-1/2 -translate-y-1/2 max-w-lg mx-auto bg-white rounded-2xl shadow-xl p-7 sm:p-8 space-y-6"
              role="dialog" aria-modal="true"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Bienvenido</p>
                  <h2 className="text-xl font-bold text-black tracking-tight">Así funciona tu consejo</h2>
                </div>
                <button onClick={close} aria-label="Cerrar" className="text-gray-400 hover:text-black transition-colors">
                  <X className="h-5 w-5" />
                </button>
              </div>

              <ol className="space-y-4">
                {STEPS.map((s, i) => {
                  const Icon = s.icon
                  return (
                    <li key={s.title} className="flex items-start gap-3.5">
                      <span className="relative shrink-0">
                        <span className="w-9 h-9 rounded-xl bg-[var(--gob-navy)]/[0.06] text-[var(--gob-navy)] flex items-center justify-center">
                          <Icon className="h-4 w-4" />
                        </span>
                        <span className="absolute -top-1.5 -left-1.5 w-4 h-4 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] text-[10px] font-bold flex items-center justify-center">{i + 1}</span>
                      </span>
                      <div className="min-w-0 pt-0.5">
                        <p className="text-sm font-semibold text-black">{s.title}</p>
                        <p className="text-sm text-gray-500 leading-relaxed">{s.desc}</p>
                      </div>
                    </li>
                  )
                })}
              </ol>

              <div className="flex items-center justify-between gap-4 pt-1">
                <button onClick={close} className="text-sm font-medium text-gray-500 hover:text-[var(--gob-navy)] transition-colors">
                  Entendido
                </button>
                <Link
                  href="/onboarding/todd"
                  onClick={close}
                  className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-5 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors"
                >
                  Empezar con Todd <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
