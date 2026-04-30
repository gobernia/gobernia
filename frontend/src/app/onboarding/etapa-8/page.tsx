"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { ChevronRight, Sparkles, Plus, X, Bot } from "lucide-react"
import ProgressBar from "@/components/onboarding/ProgressBar"
import StepWrapper from "@/components/onboarding/StepWrapper"
import GoberniaButton from "@/components/ui/GoberniaButton"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { useOnboardingStore } from "@/lib/store"
import api from "@/lib/api"

// ── Catálogos (hardcoded — coinciden con backend) ─────────
const FREQUENCIES = [
  { value: "monthly",    label: "Mensual (12 sesiones/año)" },
  { value: "bimonthly",  label: "Bimestral (6 sesiones/año)" },
  { value: "quarterly",  label: "Trimestral (4 sesiones/año)" },
  { value: "semiannual", label: "Semestral (2 sesiones/año)" },
]

const TONES: { value: string; label: string; desc: string }[] = [
  { value: "formal",        label: "Formal",        desc: "Reportes estructurados con datos precisos" },
  { value: "strategic",     label: "Estratégico",   desc: "Visión de largo plazo y tendencias" },
  { value: "direct",        label: "Directo",       desc: "Al punto, sin rodeos, alertas claras" },
  { value: "collaborative", label: "Colaborativo",  desc: "Propuestas con alternativas y consenso" },
]

const SENSITIVITIES = [
  { value: "high",   label: "Alta",   desc: "Alerta ante cualquier desviación del benchmark" },
  { value: "medium", label: "Media",  desc: "Solo umbrales críticos" },
  { value: "low",    label: "Baja",   desc: "Únicamente riesgo severo" },
]

const AGENTS = [
  { id: "CFO",     name: "CFO",     desc: "Finanzas y rentabilidad" },
  { id: "CSO",     name: "CSO",     desc: "Estrategia y posicionamiento" },
  { id: "CRO",     name: "CRO",     desc: "Riesgos y cumplimiento" },
  { id: "Auditor", name: "Auditor", desc: "Gobierno y control interno" },
]

type SubStep = "vision" | "metas" | "consejo" | "agentes"

interface AgentConfig {
  agent: string
  tone: string
  alert_sensitivity: string
  custom_instructions: string
}

export default function Etapa8Page() {
  const router = useRouter()
  const { sessionId, markStageComplete } = useOnboardingStore()
  const [subStep, setSubStep] = useState<SubStep>("vision")

  const [visionStatement, setVisionStatement] = useState("")
  const [mainGoals, setMainGoals] = useState<string[]>([""])
  const [frequency, setFrequency] = useState("")
  const [priorityTopics, setPriorityTopics] = useState<string[]>([""])
  const [successDef, setSuccessDef] = useState("")
  const [agentConfigs, setAgentConfigs] = useState<AgentConfig[]>(
    AGENTS.map(a => ({ agent: a.id, tone: "direct", alert_sensitivity: "medium", custom_instructions: "" }))
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const next = (to: SubStep) => { setError(null); setSubStep(to) }

  // Goals
  const addGoal = () => { if (mainGoals.length < 5) setMainGoals(g => [...g, ""]) }
  const setGoal = (i: number, val: string) => setMainGoals(g => g.map((x, j) => j === i ? val : x))
  const removeGoal = (i: number) => setMainGoals(g => g.filter((_, j) => j !== i))
  const canGoals = mainGoals.some(g => g.trim().length > 0)

  // Topics
  const addTopic = () => { if (priorityTopics.length < 5) setPriorityTopics(t => [...t, ""]) }
  const setTopic = (i: number, val: string) => setPriorityTopics(t => t.map((x, j) => j === i ? val : x))
  const removeTopic = (i: number) => setPriorityTopics(t => t.filter((_, j) => j !== i))
  const canConsejo = frequency !== "" && priorityTopics.some(t => t.trim().length > 0) && successDef.trim().length >= 10

  const setAgentField = (agent: string, field: keyof AgentConfig, val: string) => {
    setAgentConfigs(prev => prev.map(c => c.agent === agent ? { ...c, [field]: val } : c))
  }

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    try {
      await api.post(`/onboarding/${sessionId}/etapa-8`, {
        vision_statement: visionStatement.trim(),
        main_goals: mainGoals.filter(g => g.trim().length > 0),
        board_expectations: {
          session_frequency: frequency,
          priority_topics: priorityTopics.filter(t => t.trim().length > 0),
          success_definition: successDef.trim(),
        },
        agent_configs: agentConfigs.map(c => ({
          agent: c.agent,
          tone: c.tone,
          alert_sensitivity: c.alert_sensitivity,
          custom_instructions: c.custom_instructions.trim() || undefined,
        })),
      })
      markStageComplete(8)
      router.push("/dashboard")
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? "Ocurrió un error. Intenta de nuevo.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-xl space-y-8">
      <ProgressBar currentStep={8} />

      {/* ── Visión ── */}
      {subStep === "vision" && (
        <StepWrapper stepKey="vision">
          <div className="space-y-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-primary mb-3">
                <Sparkles className="h-5 w-5" />
                <span className="text-sm font-medium">Visión</span>
              </div>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Cuál es la visión de tu empresa?
              </h1>
              <p className="text-sm text-muted-foreground">
                En una o dos oraciones. Mínimo 20 caracteres.
              </p>
            </div>
            <textarea
              autoFocus
              placeholder="Ej. Ser la empresa líder en manufactura sustentable del norte de México para 2030."
              value={visionStatement}
              onChange={e => setVisionStatement(e.target.value)}
              maxLength={500}
              rows={4}
              className="w-full rounded-xl border-2 border-gray-200 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none resize-none transition-colors"
            />
            <div className="flex justify-between items-center">
              <span className="text-xs text-muted-foreground">{visionStatement.length}/500</span>
              {visionStatement.trim().length < 20 && visionStatement.length > 0 && (
                <span className="text-xs text-muted-foreground">{20 - visionStatement.trim().length} caracteres más</span>
              )}
            </div>
            <GoberniaButton
              onClick={() => next("metas")}
              disabled={visionStatement.trim().length < 20}
              className="w-full"
              size="lg"
            >
              Continuar <ChevronRight className="h-4 w-4" />
            </GoberniaButton>
          </div>
        </StepWrapper>
      )}

      {/* ── Metas ── */}
      {subStep === "metas" && (
        <StepWrapper stepKey="metas">
          <div className="space-y-6">
            <div className="space-y-1">
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Cuáles son tus metas principales para este año?
              </h1>
              <p className="text-sm text-muted-foreground">Entre 1 y 5 metas.</p>
            </div>
            <div className="space-y-2">
              {mainGoals.map((g, i) => (
                <div key={i} className="flex gap-2 items-center">
                  <span className="w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-bold flex items-center justify-center flex-shrink-0">
                    {i + 1}
                  </span>
                  <Input
                    autoFocus={i === mainGoals.length - 1}
                    placeholder={`Meta ${i + 1}`}
                    value={g}
                    onChange={e => setGoal(i, e.target.value)}
                    className="h-11"
                  />
                  {mainGoals.length > 1 && (
                    <button type="button" onClick={() => removeGoal(i)} className="text-muted-foreground hover:text-red-500 p-1">
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
            {mainGoals.length < 5 && (
              <button
                type="button"
                onClick={addGoal}
                className="flex items-center gap-2 text-sm text-primary hover:underline"
              >
                <Plus className="h-4 w-4" /> Agregar meta
              </button>
            )}
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => next("vision")} className="flex-1">Atrás</GoberniaButton>
              <GoberniaButton onClick={() => next("consejo")} disabled={!canGoals} className="flex-[2]" size="lg">
                Continuar <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* ── Consejo ── */}
      {subStep === "consejo" && (
        <StepWrapper stepKey="consejo">
          <div className="space-y-6">
            <div className="space-y-1">
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Cómo quieres trabajar con tu consejo?
              </h1>
            </div>

            <div className="space-y-3">
              <p className="text-sm font-medium text-foreground">Frecuencia de sesiones</p>
              <div className="grid grid-cols-1 gap-2">
                {FREQUENCIES.map(f => (
                  <motion.button
                    key={f.value}
                    type="button"
                    whileTap={{ scale: 0.97 }}
                    onClick={() => setFrequency(f.value)}
                    className={cn(
                      "w-full text-left px-4 py-3 rounded-xl border-2 text-sm font-medium transition-all duration-150",
                      frequency === f.value
                        ? "border-primary bg-primary/5 text-primary"
                        : "border-gray-200 hover:border-primary/30"
                    )}
                  >
                    {f.label}
                  </motion.button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">Temas prioritarios del consejo</p>
              {priorityTopics.map((t, i) => (
                <div key={i} className="flex gap-2 items-center">
                  <Input
                    placeholder={`Tema ${i + 1}`}
                    value={t}
                    onChange={e => setTopic(i, e.target.value)}
                    className="h-11"
                  />
                  {priorityTopics.length > 1 && (
                    <button type="button" onClick={() => removeTopic(i)} className="text-muted-foreground hover:text-red-500 p-1">
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
              ))}
              {priorityTopics.length < 5 && (
                <button type="button" onClick={addTopic} className="flex items-center gap-2 text-sm text-primary hover:underline">
                  <Plus className="h-4 w-4" /> Agregar tema
                </button>
              )}
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">¿Cómo defines el éxito de este consejo?</p>
              <textarea
                placeholder="Ej. Tomar decisiones basadas en datos y reducir riesgos operativos en 6 meses."
                value={successDef}
                onChange={e => setSuccessDef(e.target.value)}
                maxLength={400}
                rows={3}
                className="w-full rounded-xl border-2 border-gray-200 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none resize-none transition-colors"
              />
            </div>

            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => next("metas")} className="flex-1">Atrás</GoberniaButton>
              <GoberniaButton onClick={() => next("agentes")} disabled={!canConsejo} className="flex-[2]" size="lg">
                Continuar <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* ── Agentes ── */}
      {subStep === "agentes" && (
        <StepWrapper stepKey="agentes">
          <div className="space-y-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-primary mb-3">
                <Bot className="h-5 w-5" />
                <span className="text-sm font-medium">Tus agentes de IA</span>
              </div>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                Configura cómo quieres que se comuniquen
              </h1>
              <p className="text-sm text-muted-foreground">
                Personaliza el tono y sensibilidad de cada agente.
              </p>
            </div>

            {AGENTS.map(agent => {
              const config = agentConfigs.find(c => c.agent === agent.id)!
              return (
                <div key={agent.id} className="rounded-xl border-2 border-gray-100 p-4 space-y-4">
                  <div>
                    <p className="text-sm font-bold text-foreground">{agent.name}</p>
                    <p className="text-xs text-muted-foreground">{agent.desc}</p>
                  </div>

                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Tono</p>
                    <div className="grid grid-cols-2 gap-1.5">
                      {TONES.map(t => (
                        <motion.button
                          key={t.value}
                          type="button"
                          whileTap={{ scale: 0.97 }}
                          onClick={() => setAgentField(agent.id, "tone", t.value)}
                          className={cn(
                            "text-left px-3 py-2 rounded-lg border-2 transition-all duration-150",
                            config.tone === t.value
                              ? "border-primary bg-primary/5"
                              : "border-gray-200 hover:border-primary/30"
                          )}
                        >
                          <p className={cn("text-xs font-semibold", config.tone === t.value ? "text-primary" : "text-foreground")}>{t.label}</p>
                          <p className="text-xs text-muted-foreground leading-tight mt-0.5">{t.desc}</p>
                        </motion.button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Sensibilidad de alertas</p>
                    <div className="grid grid-cols-3 gap-1.5">
                      {SENSITIVITIES.map(s => (
                        <motion.button
                          key={s.value}
                          type="button"
                          whileTap={{ scale: 0.97 }}
                          onClick={() => setAgentField(agent.id, "alert_sensitivity", s.value)}
                          className={cn(
                            "text-center px-2 py-2 rounded-lg border-2 transition-all duration-150",
                            config.alert_sensitivity === s.value
                              ? "border-primary bg-primary/5"
                              : "border-gray-200 hover:border-primary/30"
                          )}
                        >
                          <p className={cn("text-xs font-semibold", config.alert_sensitivity === s.value ? "text-primary" : "text-foreground")}>{s.label}</p>
                        </motion.button>
                      ))}
                    </div>
                  </div>
                </div>
              )
            })}

            {error && <p className="text-sm text-red-500 text-center">{error}</p>}

            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => next("consejo")} className="flex-1">Atrás</GoberniaButton>
              <GoberniaButton
                onClick={handleSubmit}
                loading={loading}
                className="flex-[2]"
                size="lg"
              >
                Finalizar onboarding <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}
    </div>
  )
}
