"use client"

/**
 * Las cuatro voces del Consejo.
 *
 * El dueño ve UNA conclusión, pero puede auditar de dónde salió: aquí queda la deliberación de
 * cada consejero, con su semáforo, sus fuentes y sus preguntas. En sesiones antiguas (sin
 * conclusión) esto es lo único que hay, y se muestra abierto, como siempre.
 */
import { useState } from "react"
import { motion } from "framer-motion"
import { ChevronDown } from "lucide-react"
import {
  AGENTS,
  ALERT_COLOR,
  ALERT_LABEL,
  ALERT_ORDER,
  Analysis,
  toAlert,
  toFinding,
} from "./shared"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

export default function VocesConsejo({
  analyses,
  onChat,
  collapsible = false,
}: {
  analyses: Record<string, Analysis>
  onChat: (agentId: string) => void
  /** Con conclusión, la deliberación se pliega. Sin ella, es el análisis y va abierta. */
  collapsible?: boolean
}) {
  const [open, setOpen] = useState(!collapsible)

  const cards = (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      {AGENTS.map((a, i) => {
        const analysis = analyses[a.id]
        if (!analysis) return null
        const findings = (analysis.findings ?? []).map(toFinding)
        const alerts = (analysis.alerts ?? [])
          .map(toAlert)
          .sort((x, y) => ALERT_ORDER[x.nivel] - ALERT_ORDER[y.nivel])
        const preguntas = analysis.preguntas ?? []
        return (
          <motion.div
            key={a.id}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: EASE, delay: i * 0.07 }}
            className="border border-gray-100 hover:border-gray-300 rounded-2xl p-7 space-y-5 transition-colors flex flex-col"
          >
            <div className="flex items-center gap-3 pb-4 border-b border-gray-100">
              <span className="w-9 h-9 rounded-xl bg-[var(--gob-navy)] flex items-center justify-center shrink-0">
                <span className="text-[var(--gob-bone)] text-xs font-bold">{a.id[0]}</span>
              </span>
              <span className="min-w-0">
                <span className="block text-base font-bold text-black leading-tight">{a.id}</span>
                <span className="block text-xs text-gray-400 mt-0.5">{a.role}</span>
              </span>
              {alerts.length > 0 && (
                <span className="ml-auto flex items-center gap-1" aria-hidden>
                  {alerts.slice(0, 5).map((al, j) => (
                    <span
                      key={j}
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ backgroundColor: ALERT_COLOR[al.nivel] }}
                    />
                  ))}
                </span>
              )}
            </div>

            <p className="text-sm text-gray-600 leading-relaxed max-w-[68ch]">
              {analysis.summary}
            </p>

            {analysis._documentos_omitidos && (
              <p className="text-xs text-gray-400 leading-relaxed">
                El consejero no pudo leer los documentos de esta sesión: su análisis se apoya
                solo en el contexto y los KPIs.
              </p>
            )}

            {findings.length > 0 && (
              <div className="space-y-2">
                <p className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">
                  Hallazgos
                </p>
                <ul className="space-y-2">
                  {findings.map((f, j) => (
                    <li key={j} className="flex gap-2 text-xs text-gray-600 leading-relaxed">
                      <span className="text-gray-300 flex-shrink-0 mt-0.5">·</span>
                      <span>
                        {f.texto}
                        {f.fuente && (
                          <span className="block text-[10px] text-gray-400 italic mt-0.5">
                            Fuente: {f.fuente}
                          </span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {alerts.length > 0 && (
              <div className="space-y-2">
                <p className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">
                  Alertas
                </p>
                <ul className="space-y-2">
                  {alerts.map((al, j) => (
                    <li
                      key={j}
                      className="border-l-2 pl-3 py-0.5 text-xs leading-relaxed"
                      style={{ borderLeftColor: ALERT_COLOR[al.nivel] }}
                    >
                      <span className="sr-only">{ALERT_LABEL[al.nivel]}: </span>
                      <span className="font-medium" style={{ color: ALERT_COLOR[al.nivel] }}>
                        {al.texto}
                      </span>
                      {al.fuente && (
                        <span className="block text-[10px] text-gray-400 italic mt-0.5">
                          Fuente: {al.fuente}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {analysis.recommendations?.length > 0 && (
              <div className="space-y-2">
                <p className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">
                  Recomendaciones
                </p>
                <ul className="space-y-1.5">
                  {analysis.recommendations.map((r, j) => (
                    <li key={j} className="flex gap-2 text-xs text-gray-600 leading-relaxed">
                      <span className="text-gray-300 flex-shrink-0">→</span>
                      {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {preguntas.length > 0 && (
              <div className="space-y-2 rounded-xl bg-[var(--gob-bone)] p-4">
                <p className="text-[10px] font-medium tracking-widest text-[var(--gob-navy)] uppercase">
                  Preguntas para la junta
                </p>
                <p className="text-[10px] text-gray-500 leading-relaxed">
                  Lo que {a.id} quiere que se discuta en la sesión.
                </p>
                <ul className="space-y-1.5">
                  {preguntas.map((q, j) => (
                    <li key={j} className="flex gap-2 text-xs text-[var(--gob-ink)] leading-relaxed">
                      <span className="text-gray-400 flex-shrink-0">?</span>
                      {q}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="pt-1 mt-auto">
              <button
                onClick={() => onChat(a.id)}
                className="w-full text-xs font-medium text-gray-500 hover:text-[var(--gob-navy)] border border-gray-200 hover:border-gray-400 px-3 py-2.5 rounded-xl transition-colors"
              >
                Chatear con {a.id} →
              </button>
            </div>
          </motion.div>
        )
      })}
    </div>
  )

  if (!collapsible) return cards

  return (
    <section className="border-t border-[var(--gob-rule)] pt-6 space-y-5">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        className="group flex w-full items-center justify-between gap-4 text-left"
      >
        <span className="min-w-0">
          <span className="block text-sm font-medium text-[var(--gob-ink)]">
            Cómo lo deliberó el Consejo
          </span>
          <span className="mt-0.5 block text-xs text-[var(--gob-muted)] leading-relaxed">
            El análisis de cada consejero —CFO, CSO, CRO y Auditor— detrás de la conclusión.
          </span>
        </span>
        <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--gob-muted)] group-hover:text-[var(--gob-navy)] transition-colors flex-shrink-0">
          {open ? "Ocultar" : "Ver la deliberación"}
          <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} />
        </span>
      </button>

      {open && cards}
    </section>
  )
}
