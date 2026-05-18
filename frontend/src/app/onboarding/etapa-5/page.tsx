"use client"

import { useState, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { motion } from "framer-motion"
import { ChevronRight, BarChart3, Loader2, HelpCircle } from "lucide-react"
import ProgressBar from "@/components/onboarding/ProgressBar"
import GoberniaButton from "@/components/ui/GoberniaButton"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { useOnboardingStore } from "@/lib/store"
import api from "@/lib/api"

interface KPITemplate {
  key: string
  label: string
  dimension: string
  unit: string
  benchmark: number | null
  benchmark_label: string | null
}

interface KPIValue {
  key: string
  current_value: string
  target_value: string
  unknown: boolean
}

const DIMENSION_LABELS: Record<string, string> = {
  finance: "Finanzas",
  commercial: "Comercial",
  operations: "Operaciones",
  hr: "Capital Humano",
  governance: "Gobierno",
}

export default function Etapa5Page() {
  const router = useRouter()
  const fromDatos = useSearchParams().get("from") === "datos"
  const { sessionId, markStageComplete } = useOnboardingStore()
  const [templates, setTemplates] = useState<KPITemplate[]>([])
  const [values, setValues] = useState<Record<string, KPIValue>>({})
  const [fetching, setFetching] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionId) return
    api.get(`/onboarding/${sessionId}/etapa-5/kpis`)
      .then(r => {
        setTemplates(r.data.kpi_templates)
        const init: Record<string, KPIValue> = {}
        r.data.kpi_templates.forEach((t: KPITemplate) => {
          init[t.key] = { key: t.key, current_value: "", target_value: "", unknown: false }
        })
        setValues(init)
      })
      .catch(() => setFetchError("No se pudieron cargar los KPIs. Verifica que hayas completado la Etapa 4."))
      .finally(() => setFetching(false))
  }, [sessionId])

  const setField = (key: string, field: keyof KPIValue, val: string | boolean) => {
    setValues(prev => ({ ...prev, [key]: { ...prev[key], [field]: val } }))
  }

  const toggleUnknown = (key: string) => {
    const curr = values[key]?.unknown ?? false
    setValues(prev => ({
      ...prev,
      [key]: { ...prev[key], unknown: !curr, current_value: "", target_value: "" }
    }))
  }

  const canSubmit = Object.values(values).every(v =>
    v.unknown || v.current_value !== "" || v.target_value !== ""
  )

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    try {
      await api.post(`/onboarding/${sessionId}/etapa-5`, {
        kpis: Object.values(values).map(v => ({
          key: v.key,
          current_value: v.unknown ? null : (v.current_value !== "" ? parseFloat(v.current_value) : null),
          target_value: v.unknown ? null : (v.target_value !== "" ? parseFloat(v.target_value) : null),
          unknown: v.unknown,
        })),
      })
      markStageComplete(5)
      router.push(fromDatos ? "/dashboard/datos" : "/onboarding/etapa-6")
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
        <ProgressBar currentStep={5} />
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <Loader2 className="h-8 w-8 text-primary animate-spin" />
          <p className="text-sm text-muted-foreground">Cargando KPIs de tu industria…</p>
        </div>
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="w-full max-w-xl space-y-8">
        <ProgressBar currentStep={5} />
        <div className="text-center py-16 space-y-4">
          <p className="text-sm text-red-500">{fetchError}</p>
          <GoberniaButton variant="ghost" onClick={() => router.push("/onboarding/etapa-4")}>
            Volver a Etapa 4
          </GoberniaButton>
        </div>
      </div>
    )
  }

  // Group by dimension
  const byDimension = templates.reduce<Record<string, KPITemplate[]>>((acc, t) => {
    if (!acc[t.dimension]) acc[t.dimension] = []
    acc[t.dimension].push(t)
    return acc
  }, {})

  return (
    <div className="w-full max-w-xl space-y-8">
      <ProgressBar currentStep={5} />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        className="space-y-6"
      >
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-primary mb-3">
            <BarChart3 className="h-5 w-5" />
            <span className="text-sm font-medium">KPIs</span>
          </div>
          <h1 className="text-2xl font-bold text-foreground leading-tight">
            Ingresa tus números clave
          </h1>
          <p className="text-sm text-muted-foreground">
            Valor actual y meta. Si no lo sabes, marca "No lo sé" — el agente lo gestionará como gap.
          </p>
        </div>

        {Object.entries(byDimension).map(([dimension, kpis]) => (
          <div key={dimension} className="space-y-3">
            <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide border-b border-gray-100 pb-2">
              {DIMENSION_LABELS[dimension] ?? dimension}
            </h2>
            {kpis.map(t => {
              const v = values[t.key]
              if (!v) return null
              return (
                <div key={t.key} className="rounded-xl border-2 border-gray-100 p-4 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-foreground">{t.label}</p>
                      {t.benchmark_label && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Benchmark: {t.benchmark_label}
                        </p>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => toggleUnknown(t.key)}
                      className={cn(
                        "flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border transition-all flex-shrink-0",
                        v.unknown
                          ? "border-primary/30 bg-primary/5 text-primary"
                          : "border-gray-200 text-muted-foreground hover:border-gray-300"
                      )}
                    >
                      <HelpCircle className="h-3 w-3" />
                      No lo sé
                    </button>
                  </div>

                  {!v.unknown && (
                    <div className="grid grid-cols-2 gap-2">
                      <div className="space-y-1">
                        <label className="text-xs text-muted-foreground">
                          Actual ({t.unit})
                        </label>
                        <Input
                          type="number"
                          placeholder="0"
                          value={v.current_value}
                          onChange={e => setField(t.key, "current_value", e.target.value)}
                          className="h-10 text-sm"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs text-muted-foreground">
                          Meta ({t.unit})
                        </label>
                        <Input
                          type="number"
                          placeholder="0"
                          value={v.target_value}
                          onChange={e => setField(t.key, "target_value", e.target.value)}
                          className="h-10 text-sm"
                        />
                      </div>
                    </div>
                  )}

                  {v.unknown && (
                    <p className="text-xs text-primary bg-primary/5 px-3 py-2 rounded-lg">
                      El agente identificará este KPI como gap prioritario.
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        ))}

        {error && <p className="text-sm text-red-500 text-center">{error}</p>}

        <div className="flex gap-3">
          <GoberniaButton variant="ghost" onClick={() => router.push("/onboarding/etapa-4")} className="flex-1">
            Atrás
          </GoberniaButton>
          <GoberniaButton
            onClick={handleSubmit}
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
