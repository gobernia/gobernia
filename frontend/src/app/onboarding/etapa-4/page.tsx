"use client"

import { useState, useEffect, useRef } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { ChevronRight, ClipboardList, Loader2, Info } from "lucide-react"
import ProgressBar from "@/components/onboarding/ProgressBar"
import StepWrapper from "@/components/onboarding/StepWrapper"
import GoberniaButton from "@/components/ui/GoberniaButton"
import { cn } from "@/lib/utils"
import { useOnboardingStore } from "@/lib/store"
import api from "@/lib/api"

interface Question {
  question_id: string
  area: string
  text: string
  description?: string
  response_options: string[]
}

const OPTION_LABELS: Record<string, string> = {
  yes: "Sí",
  partial: "Parcialmente",
  no: "No",
  unknown: "No lo sé",
}

function InfoTooltip({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [open])

  return (
    <span className="relative inline-flex items-center">
      <button
        ref={ref}
        type="button"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onClick={() => setOpen(v => !v)}
        className="inline-flex items-center gap-1 rounded-full border border-gray-300 hover:border-black bg-white hover:bg-gray-50 px-2 py-0.5 text-[11px] font-medium text-gray-500 hover:text-black transition-all flex-shrink-0"
        aria-label="Más información"
      >
        <Info className="w-3 h-3" />
        ¿Qué evalúa?
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className="absolute left-0 bottom-full mb-2 z-50 w-72 bg-gray-900 text-white text-xs leading-relaxed rounded-xl px-3.5 py-3 shadow-xl pointer-events-none"
          >
            {text}
            <span className="absolute left-4 top-full w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-gray-900" />
          </motion.div>
        )}
      </AnimatePresence>
    </span>
  )
}

export default function Etapa4Page() {
  const router = useRouter()
  const fromDatos = useSearchParams().get("from") === "datos"
  const { sessionId, markStageComplete } = useOnboardingStore()
  const [questions, setQuestions] = useState<Question[]>([])
  const [current, setCurrent] = useState(0)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [fetching, setFetching] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionId) return
    api.get(`/onboarding/${sessionId}/etapa-4/questions`)
      .then(r => setQuestions(r.data.questions))
      .catch(() => setFetchError("No se pudieron cargar las preguntas. Verifica que hayas completado la Etapa 3."))
      .finally(() => setFetching(false))
  }, [sessionId])

  const q = questions[current]
  const answered = q ? answers[q.question_id] !== undefined : false
  const isLast = current === questions.length - 1

  const selectAnswer = (qid: string, value: string) => {
    setAnswers(prev => ({ ...prev, [qid]: value }))
  }

  const skipQuestion = () => {
    setAnswers(prev => ({ ...prev, [q.question_id]: "skipped" }))
    if (isLast) handleSubmit({ ...answers, [q.question_id]: "skipped" })
    else setCurrent(c => c + 1)
  }

  const goNext = () => {
    if (isLast) handleSubmit(answers)
    else setCurrent(c => c + 1)
  }

  const handleSubmit = async (finalAnswers: Record<string, string>) => {
    setLoading(true)
    setError(null)
    try {
      await api.post(`/onboarding/${sessionId}/etapa-4`, {
        responses: Object.entries(finalAnswers).map(([question_id, response]) => ({
          question_id,
          response,
        })),
      })
      markStageComplete(4)
      router.push(fromDatos ? "/dashboard/datos" : "/onboarding/etapa-5")
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? "Ocurrió un error. Intenta de nuevo.")
      setLoading(false)
    }
  }

  if (fetching) {
    return (
      <div className="w-full max-w-xl space-y-8">
        <ProgressBar currentStep={4} />
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <Loader2 className="h-8 w-8 text-primary animate-spin" />
          <p className="text-sm text-muted-foreground">Generando tu diagnóstico personalizado…</p>
        </div>
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="w-full max-w-xl space-y-8">
        <ProgressBar currentStep={4} />
        <div className="text-center py-16 space-y-4">
          <p className="text-sm text-red-500">{fetchError}</p>
          <GoberniaButton variant="ghost" onClick={() => router.push("/onboarding/etapa-3")}>
            Volver a Etapa 3
          </GoberniaButton>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full max-w-xl space-y-8">
      <ProgressBar currentStep={4} />

      {q && (
        <StepWrapper stepKey={q.question_id}>
          <div className="space-y-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-primary mb-3">
                <ClipboardList className="h-5 w-5" />
                <span className="text-sm font-medium">
                  Diagnóstico — {current + 1} / {questions.length}
                </span>
              </div>

              {/* Progress bar for questions */}
              <div className="h-1 bg-gray-100 rounded-full overflow-hidden mb-4">
                <motion.div
                  className="h-full bg-primary rounded-full"
                  animate={{ width: `${((current + 1) / questions.length) * 100}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>

              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                {q.area}
              </p>
              <h1 className="text-xl font-bold text-foreground leading-snug mt-1">
                {q.text}
              </h1>
              {q.description && (
                <div className="mt-2">
                  <InfoTooltip text={q.description} />
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 gap-2">
              {q.response_options.map(opt => {
                const label = OPTION_LABELS[opt] ?? opt
                const selected = answers[q.question_id] === opt
                return (
                  <motion.button
                    key={opt}
                    type="button"
                    whileTap={{ scale: 0.97 }}
                    onClick={() => selectAnswer(q.question_id, opt)}
                    className={cn(
                      "w-full text-left px-4 py-3.5 rounded-xl border-2 text-sm font-medium",
                      "transition-all duration-150 cursor-pointer",
                      selected
                        ? "border-primary bg-primary/5 text-primary"
                        : "border-gray-200 bg-white text-foreground hover:border-primary/40 hover:bg-gray-50"
                    )}
                  >
                    <span className="flex items-center gap-3">
                      <span className={cn(
                        "w-4 h-4 rounded-full border-2 flex-shrink-0 transition-all",
                        selected ? "border-primary bg-primary" : "border-gray-300"
                      )}>
                        {selected && (
                          <motion.span
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            className="block w-full h-full rounded-full bg-white scale-[0.4]"
                          />
                        )}
                      </span>
                      {label}
                    </span>
                  </motion.button>
                )
              })}
            </div>

            {error && <p className="text-sm text-red-500 text-center">{error}</p>}

            <div className="flex gap-3">
              <GoberniaButton
                variant="ghost"
                onClick={() => current === 0 ? router.push("/onboarding/etapa-3") : setCurrent(c => c - 1)}
                className="flex-1"
              >
                Atrás
              </GoberniaButton>
              <GoberniaButton
                variant="ghost"
                onClick={skipQuestion}
                className="flex-1 text-gray-400 hover:text-gray-600"
              >
                Saltar
              </GoberniaButton>
              <GoberniaButton
                onClick={goNext}
                disabled={!answered}
                loading={loading && isLast}
                className="flex-[2]"
                size="lg"
              >
                {isLast ? "Guardar y continuar" : "Siguiente"} <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}
    </div>
  )
}
