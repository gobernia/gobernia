"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

const AGENTS = [
  { id: "CFO", role: "Finanzas" },
  { id: "CSO", role: "Estrategia" },
  { id: "CRO", role: "Riesgos" },
  { id: "Auditor", role: "Gobierno" },
]

const PIPELINE_AGENTS = ["CFO", "CSO", "CRO", "Auditor"] as const
const PHASES = ["analiza", "challenge", "revisa"] as const
type Phase = (typeof PHASES)[number]
type PipelineAgent = (typeof PIPELINE_AGENTS)[number]

const AGENT_ANGLES: Record<PipelineAgent, number> = {
  CFO: 270, CSO: 0, CRO: 90, Auditor: 180,
}

const PHASE_COPY: Record<Phase, (agent: PipelineAgent) => string> = {
  analiza:   a => `${a} está analizando tu información…`,
  challenge: a => `El Retador aplica pre-mortem al ${a}…`,
  revisa:    a => `${a} revisa su análisis con la crítica…`,
}

export default function AgentsCollaboration({
  caption = "Cada consejero entrega su diagnóstico al Retador, que imagina cómo podría fracasar en 12 meses y devuelve la crítica antes de mostrarte el resultado.",
}: {
  caption?: string
}) {
  const [step, setStep] = useState(0)

  useEffect(() => {
    const t = setInterval(() => setStep(s => s + 1), 1400)
    return () => clearInterval(t)
  }, [])

  const agent = PIPELINE_AGENTS[Math.floor(step / 3) % PIPELINE_AGENTS.length]
  const phase = PHASES[step % PHASES.length]

  const size = 260
  const radius = 100
  const c = size / 2

  const pos = (a: PipelineAgent) => {
    const rad = (AGENT_ANGLES[a] * Math.PI) / 180
    return { x: c + radius * Math.cos(rad), y: c + radius * Math.sin(rad) }
  }

  const active = pos(agent)
  const packetFrom = phase === "challenge" ? active : { x: c, y: c }
  const packetTo   = phase === "challenge" ? { x: c, y: c } : active

  return (
    <div className="flex flex-col items-center gap-7">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="absolute inset-0 overflow-visible">
          {PIPELINE_AGENTS.map(a => {
            const p = pos(a)
            const isActive = a === agent
            return (
              <line
                key={a}
                x1={c} y1={c} x2={p.x} y2={p.y}
                stroke={isActive ? "#000" : "#e5e7eb"}
                strokeWidth={isActive ? 1.5 : 1}
                strokeDasharray={isActive ? "0" : "3 4"}
              />
            )
          })}
          <circle cx={c} cy={c} r={radius} fill="none" stroke="#f3f4f6" strokeWidth={1} />
          <motion.circle
            key={`${agent}-${phase}-${step}`}
            r={4}
            fill="#000"
            initial={{ cx: packetFrom.x, cy: packetFrom.y, opacity: 0 }}
            animate={{
              cx: [packetFrom.x, packetTo.x],
              cy: [packetFrom.y, packetTo.y],
              opacity: [0, 1, 1, 0],
            }}
            transition={{ duration: 1.2, ease: EASE, times: [0, 0.15, 0.85, 1] }}
          />
        </svg>

        {PIPELINE_AGENTS.map(a => {
          const p = pos(a)
          const isActive = a === agent
          const meta = AGENTS.find(x => x.id === a)!
          return (
            <motion.div
              key={a}
              className="absolute flex flex-col items-center pointer-events-none"
              style={{ left: p.x - 28, top: p.y - 28, width: 56 }}
              animate={{ scale: isActive ? 1.1 : 1 }}
              transition={{ duration: 0.35, ease: EASE }}
            >
              <div className={`w-12 h-12 rounded-2xl border-2 flex items-center justify-center transition-colors ${
                isActive
                  ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                  : "border-gray-200 bg-white text-gray-400"
              }`}>
                <span className="text-sm font-bold">{a[0]}</span>
              </div>
              <span className={`text-[9px] mt-1.5 font-medium tracking-wide ${isActive ? "text-black" : "text-gray-400"}`}>{a}</span>
              <span className="text-[8px] text-gray-300 leading-none mt-0.5">{meta.role}</span>
            </motion.div>
          )
        })}

        <motion.div
          className="absolute flex flex-col items-center pointer-events-none"
          style={{ left: c - 34, top: c - 34, width: 68 }}
          animate={{ scale: phase === "challenge" ? 1.12 : 1 }}
          transition={{ duration: 0.35, ease: EASE }}
        >
          <div className={`w-14 h-14 rounded-2xl border-2 flex items-center justify-center transition-colors ${
            phase === "challenge"
              ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
              : "border-gray-300 bg-white text-gray-500"
          }`}>
            <span className="text-[10px] font-black tracking-tight">PRE</span>
          </div>
          <span className={`text-[9px] mt-1.5 font-medium tracking-wide ${phase === "challenge" ? "text-black" : "text-gray-500"}`}>Retador</span>
          <span className="text-[8px] text-gray-400 leading-none mt-0.5">Pre-mortem</span>
        </motion.div>
      </div>

      <div className="space-y-2 text-center max-w-md">
        <motion.p
          key={`${agent}-${phase}`}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: EASE }}
          className="text-sm font-medium text-black"
        >
          {PHASE_COPY[phase](agent)}
        </motion.p>
        <p className="text-xs text-gray-400 leading-relaxed">{caption}</p>

        <div className="flex items-center justify-center gap-4 pt-3">
          {PIPELINE_AGENTS.map(a => (
            <div key={a} className="flex items-center gap-1.5">
              <span className={`text-[10px] font-medium tracking-wide ${a === agent ? "text-black" : "text-gray-300"}`}>{a}</span>
              <div className="flex gap-0.5">
                {PHASES.map((p, i) => {
                  const ai = PIPELINE_AGENTS.indexOf(a)
                  const cur = PIPELINE_AGENTS.indexOf(agent)
                  const done = ai < cur || (ai === cur && i < PHASES.indexOf(phase))
                  const isNow = a === agent && p === phase
                  return (
                    <div key={p} className={`h-1 w-3 rounded-full transition-colors ${
                      isNow ? "bg-[var(--gob-navy)]" : done ? "bg-gray-400" : "bg-gray-100"
                    }`} />
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
