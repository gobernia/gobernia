"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { ChevronRight, Target, X, GripVertical } from "lucide-react"
import ProgressBar from "@/components/onboarding/ProgressBar"
import StepWrapper from "@/components/onboarding/StepWrapper"
import GoberniaButton from "@/components/ui/GoberniaButton"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { useOnboardingStore } from "@/lib/store"
import api from "@/lib/api"

const CHALLENGES = [
  { value: "commercial_growth",      label: "Crecimiento comercial y ventas" },
  { value: "profitability",          label: "Rentabilidad y márgenes" },
  { value: "talent",                 label: "Talento y equipo directivo" },
  { value: "operations",             label: "Eficiencia operativa" },
  { value: "organizational_clarity", label: "Claridad organizacional" },
  { value: "delegation_succession",  label: "Delegación y sucesión" },
  { value: "market_position",        label: "Posicionamiento de mercado" },
  { value: "compliance_risk",        label: "Cumplimiento y riesgos legales" },
  { value: "innovation_technology",  label: "Innovación y tecnología" },
  { value: "other",                  label: "Otro" },
]

interface Priority {
  challenge: string
  challenge_custom: string
  rank: number
}

type SubStep = "seleccionar" | "otro"

export default function Etapa3Page() {
  const router = useRouter()
  const { sessionId, markStageComplete } = useOnboardingStore()
  const [subStep, setSubStep] = useState<SubStep>("seleccionar")
  const [selected, setSelected] = useState<Priority[]>([])
  const [customText, setCustomText] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const toggle = (value: string) => {
    const exists = selected.find(s => s.challenge === value)
    if (exists) {
      const removed = selected.filter(s => s.challenge !== value)
      setSelected(removed.map((p, i) => ({ ...p, rank: i + 1 })))
    } else if (selected.length < 5) {
      if (value === "other") {
        setSubStep("otro")
        return
      }
      setSelected(prev => [...prev, { challenge: value, challenge_custom: "", rank: prev.length + 1 }])
    }
  }

  const addOther = () => {
    if (customText.trim().length < 2) return
    setSelected(prev => [...prev, {
      challenge: "other",
      challenge_custom: customText.trim(),
      rank: prev.length + 1,
    }])
    setCustomText("")
    setSubStep("seleccionar")
  }

  const remove = (rank: number) => {
    const removed = selected.filter(p => p.rank !== rank)
    setSelected(removed.map((p, i) => ({ ...p, rank: i + 1 })))
  }

  const moveUp = (idx: number) => {
    if (idx === 0) return
    const next = [...selected]
    ;[next[idx - 1], next[idx]] = [next[idx], next[idx - 1]]
    setSelected(next.map((p, i) => ({ ...p, rank: i + 1 })))
  }

  const moveDown = (idx: number) => {
    if (idx === selected.length - 1) return
    const next = [...selected]
    ;[next[idx], next[idx + 1]] = [next[idx + 1], next[idx]]
    setSelected(next.map((p, i) => ({ ...p, rank: i + 1 })))
  }

  const canSubmit = selected.length >= 3

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    try {
      await api.post(`/onboarding/${sessionId}/etapa-3`, {
        priorities: selected.map(p => ({
          challenge: p.challenge,
          challenge_custom: p.challenge === "other" ? p.challenge_custom : undefined,
          rank: p.rank,
        })),
      })
      markStageComplete(3)
      router.push("/onboarding/etapa-4")
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? "Ocurrió un error. Intenta de nuevo.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-xl space-y-8">
      <ProgressBar currentStep={3} />

      {/* Seleccionar retos */}
      {subStep === "seleccionar" && (
        <StepWrapper stepKey="seleccionar">
          <div className="space-y-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-primary mb-3">
                <Target className="h-5 w-5" />
                <span className="text-sm font-medium">Prioridades</span>
              </div>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Cuáles son los principales retos de tu empresa?
              </h1>
              <p className="text-sm text-muted-foreground">
                Selecciona entre 3 y 5. El orden en que los agregues define su importancia.
              </p>
            </div>

            {/* Ranking actual */}
            <AnimatePresence>
              {selected.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  className="space-y-2"
                >
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                    Tu ranking actual
                  </p>
                  {selected.map((p, idx) => {
                    const label = p.challenge === "other"
                      ? p.challenge_custom
                      : CHALLENGES.find(c => c.value === p.challenge)?.label
                    return (
                      <motion.div
                        key={p.challenge}
                        layout
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 8 }}
                        className="flex items-center gap-2 px-3 py-2.5 bg-primary/5 border-2 border-primary/20 rounded-xl"
                      >
                        <span className="w-6 h-6 rounded-full bg-primary text-white text-xs font-bold flex items-center justify-center flex-shrink-0">
                          {p.rank}
                        </span>
                        <span className="flex-1 text-sm font-medium text-foreground">{label}</span>
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => moveUp(idx)}
                            disabled={idx === 0}
                            className="p-1 text-muted-foreground hover:text-foreground disabled:opacity-20"
                          >
                            <GripVertical className="h-3.5 w-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => remove(p.rank)}
                            className="p-1 text-muted-foreground hover:text-red-500"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </motion.div>
                    )
                  })}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Opciones disponibles */}
            {selected.length < 5 && (
              <div className="grid grid-cols-1 gap-2">
                {CHALLENGES.filter(c => !selected.find(s => s.challenge === c.value)).map(opt => (
                  <motion.button
                    key={opt.value}
                    type="button"
                    whileTap={{ scale: 0.97 }}
                    onClick={() => toggle(opt.value)}
                    className="w-full text-left px-4 py-3.5 rounded-xl border-2 border-gray-200 bg-white text-sm font-medium text-foreground hover:border-primary/40 hover:bg-gray-50 transition-all duration-150"
                  >
                    {opt.label}
                  </motion.button>
                ))}
              </div>
            )}

            {selected.length >= 5 && (
              <p className="text-xs text-muted-foreground text-center">
                Máximo 5 prioridades seleccionadas.
              </p>
            )}

            {error && <p className="text-sm text-red-500 text-center">{error}</p>}

            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => router.push("/onboarding/etapa-2")} className="flex-1">
                Atrás
              </GoberniaButton>
              <GoberniaButton
                onClick={handleSubmit}
                disabled={!canSubmit}
                loading={loading}
                className="flex-[2]"
                size="lg"
              >
                Guardar y continuar <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>

            {!canSubmit && selected.length > 0 && (
              <p className="text-xs text-center text-muted-foreground">
                Selecciona al menos {3 - selected.length} más
              </p>
            )}
          </div>
        </StepWrapper>
      )}

      {/* Otro — texto libre */}
      {subStep === "otro" && (
        <StepWrapper stepKey="otro">
          <div className="space-y-6">
            <div className="space-y-1">
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Cuál es ese otro reto?
              </h1>
              <p className="text-sm text-muted-foreground">Descríbelo brevemente.</p>
            </div>
            <Input
              autoFocus
              placeholder="Ej. Digitalización de procesos internos"
              value={customText}
              onChange={e => setCustomText(e.target.value)}
              className="h-12 text-base"
              onKeyDown={e => e.key === "Enter" && customText.trim().length >= 2 && addOther()}
            />
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => setSubStep("seleccionar")} className="flex-1">
                Cancelar
              </GoberniaButton>
              <GoberniaButton
                onClick={addOther}
                disabled={customText.trim().length < 2}
                className="flex-[2]"
                size="lg"
              >
                Agregar <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}
    </div>
  )
}
