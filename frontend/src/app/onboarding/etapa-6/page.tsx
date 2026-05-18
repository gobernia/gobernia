"use client"

import { useState, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { motion } from "framer-motion"
import { ChevronRight, Shield, Loader2 } from "lucide-react"
import ProgressBar from "@/components/onboarding/ProgressBar"
import GoberniaButton from "@/components/ui/GoberniaButton"
import { cn } from "@/lib/utils"
import { useOnboardingStore } from "@/lib/store"
import api from "@/lib/api"

interface GovernanceItem {
  key: string
  label: string
  description: string
  dimension: string
}

type GovernanceResponse = "yes" | "partial" | "no" | "na"

const RESPONSE_OPTIONS: { value: GovernanceResponse; label: string }[] = [
  { value: "yes",     label: "Sí" },
  { value: "partial", label: "Parcial" },
  { value: "no",      label: "No" },
  { value: "na",      label: "N/A" },
]

const DIMENSION_LABELS: Record<string, string> = {
  board:         "Consejo",
  compliance:    "Cumplimiento",
  documentation: "Documentación",
  family:        "Protocolo Familiar",
}

export default function Etapa6Page() {
  const router = useRouter()
  const fromDatos = useSearchParams().get("from") === "datos"
  const { sessionId, markStageComplete } = useOnboardingStore()
  const [items, setItems] = useState<GovernanceItem[]>([])
  const [answers, setAnswers] = useState<Record<string, GovernanceResponse>>({})
  const [fetching, setFetching] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionId) return
    api.get(`/onboarding/${sessionId}/etapa-6/items`)
      .then(r => setItems(r.data.items))
      .catch(() => setFetchError("No se pudieron cargar los ítems. Verifica que hayas completado la Etapa 5."))
      .finally(() => setFetching(false))
  }, [sessionId])

  const setAnswer = (key: string, value: GovernanceResponse) => {
    setAnswers(prev => ({ ...prev, [key]: value }))
  }

  const canSubmit = items.length > 0 && items.every(i => answers[i.key] !== undefined)

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    try {
      await api.post(`/onboarding/${sessionId}/etapa-6`, {
        items: Object.entries(answers).map(([key, response]) => ({ key, response })),
      })
      markStageComplete(6)
      router.push(fromDatos ? "/dashboard/datos" : "/onboarding/etapa-7")
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? "Ocurrió un error. Intenta de nuevo.")
    } finally {
      setLoading(false)
    }
  }

  if (fetching) {
    return (
      <div className="w-full max-w-xl space-y-8">
        <ProgressBar currentStep={6} />
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <Loader2 className="h-8 w-8 text-primary animate-spin" />
          <p className="text-sm text-muted-foreground">Cargando checklist de gobierno…</p>
        </div>
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="w-full max-w-xl space-y-8">
        <ProgressBar currentStep={6} />
        <div className="text-center py-16 space-y-4">
          <p className="text-sm text-red-500">{fetchError}</p>
          <GoberniaButton variant="ghost" onClick={() => router.push("/onboarding/etapa-5")}>
            Volver a Etapa 5
          </GoberniaButton>
        </div>
      </div>
    )
  }

  const byDimension = items.reduce<Record<string, GovernanceItem[]>>((acc, i) => {
    if (!acc[i.dimension]) acc[i.dimension] = []
    acc[i.dimension].push(i)
    return acc
  }, {})

  const answered = Object.keys(answers).length
  const total = items.length

  return (
    <div className="w-full max-w-xl space-y-8">
      <ProgressBar currentStep={6} />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        className="space-y-6"
      >
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-primary mb-3">
            <Shield className="h-5 w-5" />
            <span className="text-sm font-medium">Gobierno Corporativo</span>
          </div>
          <h1 className="text-2xl font-bold text-foreground leading-tight">
            Checklist de gobierno
          </h1>
          <p className="text-sm text-muted-foreground">
            Responde honestamente — esto genera tu Governance Score.
          </p>

          {/* Progress pill */}
          <div className="flex items-center gap-2 mt-3">
            <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-primary rounded-full"
                animate={{ width: `${(answered / total) * 100}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
            <span className="text-xs text-muted-foreground tabular-nums">{answered}/{total}</span>
          </div>
        </div>

        {Object.entries(byDimension).map(([dimension, dimItems]) => (
          <div key={dimension} className="space-y-3">
            <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide border-b border-gray-100 pb-2">
              {DIMENSION_LABELS[dimension] ?? dimension}
            </h2>
            {dimItems.map(item => {
              const selected = answers[item.key]
              return (
                <div key={item.key} className="rounded-xl border-2 border-gray-100 p-4 space-y-3">
                  <div>
                    <p className="text-sm font-semibold text-foreground">{item.label}</p>
                    {item.description && (
                      <p className="text-xs text-muted-foreground mt-0.5">{item.description}</p>
                    )}
                  </div>
                  <div className="grid grid-cols-4 gap-1.5">
                    {RESPONSE_OPTIONS.map(opt => (
                      <motion.button
                        key={opt.value}
                        type="button"
                        whileTap={{ scale: 0.95 }}
                        onClick={() => setAnswer(item.key, opt.value)}
                        className={cn(
                          "py-2 rounded-lg border-2 text-xs font-medium transition-all duration-150",
                          selected === opt.value
                            ? "border-primary bg-primary/5 text-primary"
                            : "border-gray-200 text-muted-foreground hover:border-primary/30"
                        )}
                      >
                        {opt.label}
                      </motion.button>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        ))}

        {error && <p className="text-sm text-red-500 text-center">{error}</p>}

        <div className="flex gap-3">
          <GoberniaButton variant="ghost" onClick={() => router.push("/onboarding/etapa-5")} className="flex-1">
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
      </motion.div>
    </div>
  )
}
