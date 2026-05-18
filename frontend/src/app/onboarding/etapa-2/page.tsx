"use client"

import { useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { ChevronRight, UserPlus, Trash2, Check, Users } from "lucide-react"
import ProgressBar from "@/components/onboarding/ProgressBar"
import StepWrapper from "@/components/onboarding/StepWrapper"
import GoberniaButton from "@/components/ui/GoberniaButton"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { useOnboardingStore } from "@/lib/store"
import api from "@/lib/api"

// ── Catálogos ─────────────────────────────────────────────
const ROLES = [
  { value: "ceo",               label: "CEO / Director General" },
  { value: "cfo",               label: "CFO / Director Financiero" },
  { value: "operations",        label: "Director de Operaciones" },
  { value: "commercial",        label: "Director Comercial / Ventas" },
  { value: "hr",                label: "Director de Recursos Humanos" },
  { value: "shareholder",       label: "Accionista / Socio" },
  { value: "external_advisor",  label: "Consejero / Asesor externo" },
  { value: "other",             label: "Otro" },
]

interface TeamMember {
  name: string
  role: string
  role_custom: string
  is_family: boolean | null
  makes_key_decisions: boolean | null
  email: string
}

type MemberSubStep = "nombre" | "rol" | "familiar" | "decisiones" | "email"

const EMPTY_MEMBER: TeamMember = {
  name: "",
  role: "",
  role_custom: "",
  is_family: null,
  makes_key_decisions: null,
  email: "",
}

function OptionCard({
  selected, onClick, label,
}: { selected: boolean; onClick: () => void; label: string }) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      whileTap={{ scale: 0.97 }}
      className={cn(
        "w-full text-left px-4 py-3.5 rounded-xl border-2 text-sm font-medium",
        "transition-all duration-150 cursor-pointer",
        selected
          ? "border-primary bg-primary/5 text-primary"
          : "border-gray-200 bg-white text-foreground hover:border-primary/40 hover:bg-gray-50"
      )}
    >
      <span className="flex items-center gap-3">
        <span
          className={cn(
            "w-4 h-4 rounded-full border-2 flex-shrink-0 transition-all",
            selected ? "border-primary bg-primary" : "border-gray-300"
          )}
        >
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
}

function MemberCard({
  member, index, onRemove,
}: { member: TeamMember; index: number; onRemove: () => void }) {
  const roleLabel = ROLES.find(r => r.value === member.role)?.label ?? member.role_custom
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className="flex items-center justify-between px-4 py-3 rounded-xl border-2 border-gray-100 bg-gray-50"
    >
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
          <span className="text-xs font-bold text-primary">{index + 1}</span>
        </div>
        <div>
          <p className="text-sm font-semibold text-foreground">{member.name}</p>
          <p className="text-xs text-muted-foreground">{roleLabel}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {member.makes_key_decisions && (
          <span className="text-xs bg-primary/10 text-primary font-medium px-2 py-0.5 rounded-full">
            Decisor
          </span>
        )}
        <button
          type="button"
          onClick={onRemove}
          className="text-gray-400 hover:text-red-500 transition-colors p-1"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </motion.div>
  )
}

export default function Etapa2Page() {
  const router = useRouter()
  const fromDatos = useSearchParams().get("from") === "datos"
  const { sessionId, markStageComplete } = useOnboardingStore()
  const [members, setMembers] = useState<TeamMember[]>([])
  const [adding, setAdding] = useState(false)
  const [memberStep, setMemberStep] = useState<MemberSubStep>("nombre")
  const [current, setCurrent] = useState<TeamMember>(EMPTY_MEMBER)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const startAdding = () => {
    setCurrent(EMPTY_MEMBER)
    setMemberStep("nombre")
    setAdding(true)
  }

  const cancelAdding = () => {
    setAdding(false)
  }

  const nextMemberStep = (to: MemberSubStep) => setMemberStep(to)

  const finishMember = () => {
    setMembers(prev => [...prev, current])
    setAdding(false)
  }

  const removeMember = (i: number) => {
    setMembers(prev => prev.filter((_, idx) => idx !== i))
  }

  const hasDecisionMaker = members.some(m => m.makes_key_decisions)
  const canSubmit = members.length >= 1 && hasDecisionMaker

  const handleSubmit = async () => {
    if (!canSubmit) return
    setLoading(true)
    setError(null)
    try {
      await api.post(`/onboarding/${sessionId}/etapa-2`, {
        team: members.map(m => ({
          name: m.name.trim(),
          role: m.role,
          role_custom: m.role === "other" ? m.role_custom.trim() : undefined,
          is_family: m.is_family === true,
          makes_key_decisions: m.makes_key_decisions === true,
          email: m.email.trim() || undefined,
        })),
      })
      markStageComplete(2)
      router.push(fromDatos ? "/dashboard/datos" : "/onboarding/etapa-3")
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? "Ocurrió un error. Intenta de nuevo.")
    } finally {
      setLoading(false)
    }
  }

  // ── Vista principal (lista de miembros) ──
  if (!adding) {
    return (
      <div className="w-full max-w-xl space-y-8">
        <ProgressBar currentStep={2} />
        <StepWrapper stepKey="team-list">
          <div className="space-y-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-primary mb-3">
                <Users className="h-5 w-5" />
                <span className="text-sm font-medium">Equipo directivo</span>
              </div>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Quiénes forman el equipo que toma decisiones?
              </h1>
              <p className="text-sm text-muted-foreground">
                Agrega a los directivos, socios y consejeros principales. Mínimo uno.
              </p>
            </div>

            {/* Member list */}
            <AnimatePresence>
              {members.length === 0 ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-center py-10 rounded-xl border-2 border-dashed border-gray-200 text-muted-foreground text-sm"
                >
                  Aún no has agregado ningún miembro
                </motion.div>
              ) : (
                <div className="space-y-2">
                  {members.map((m, i) => (
                    <MemberCard
                      key={i}
                      member={m}
                      index={i}
                      onRemove={() => removeMember(i)}
                    />
                  ))}
                </div>
              )}
            </AnimatePresence>

            {/* Validation hints */}
            {members.length >= 1 && !hasDecisionMaker && (
              <p className="text-xs text-amber-600 bg-amber-50 px-3 py-2 rounded-lg border border-amber-200">
                Al menos un miembro debe tomar decisiones clave en la empresa.
              </p>
            )}

            {/* Add button */}
            {members.length < 20 && (
              <GoberniaButton
                variant="secondary"
                onClick={startAdding}
                className="w-full"
                size="lg"
              >
                <UserPlus className="h-4 w-4" />
                {members.length === 0 ? "Agregar primer miembro" : "Agregar otro miembro"}
              </GoberniaButton>
            )}

            {error && <p className="text-sm text-red-500 text-center">{error}</p>}

            <div className="flex gap-3">
              <GoberniaButton
                variant="ghost"
                onClick={() => router.push("/onboarding/etapa-1")}
                className="flex-1"
              >
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
          </div>
        </StepWrapper>
      </div>
    )
  }

  // ── Vista: agregar miembro (sub-pasos) ──
  return (
    <div className="w-full max-w-xl space-y-8">
      <ProgressBar currentStep={2} />

      {/* Nombre del miembro */}
      {memberStep === "nombre" && (
        <StepWrapper stepKey="m-nombre">
          <div className="space-y-6">
            <div className="space-y-1">
              <p className="text-xs font-semibold text-primary uppercase tracking-wide">
                Miembro #{members.length + 1}
              </p>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Cómo se llama esta persona?
              </h1>
            </div>
            <Input
              autoFocus
              placeholder="Nombre completo"
              value={current.name}
              onChange={e => setCurrent(c => ({ ...c, name: e.target.value }))}
              className="h-12 text-base"
              onKeyDown={e =>
                e.key === "Enter" && current.name.trim().length >= 2 && nextMemberStep("rol")
              }
            />
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={cancelAdding} className="flex-1">
                Cancelar
              </GoberniaButton>
              <GoberniaButton
                onClick={() => nextMemberStep("rol")}
                disabled={current.name.trim().length < 2}
                className="flex-[2]"
                size="lg"
              >
                Continuar <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* Rol del miembro */}
      {memberStep === "rol" && (
        <StepWrapper stepKey="m-rol">
          <div className="space-y-6">
            <div className="space-y-1">
              <p className="text-xs font-semibold text-primary uppercase tracking-wide">
                {current.name}
              </p>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Cuál es su rol en la empresa?
              </h1>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {ROLES.map(opt => (
                <OptionCard
                  key={opt.value}
                  selected={current.role === opt.value}
                  onClick={() => setCurrent(c => ({ ...c, role: opt.value }))}
                  label={opt.label}
                />
              ))}
            </div>
            {current.role === "other" && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}>
                <Input
                  autoFocus
                  placeholder="Describe el rol"
                  value={current.role_custom}
                  onChange={e => setCurrent(c => ({ ...c, role_custom: e.target.value }))}
                  className="h-11"
                />
              </motion.div>
            )}
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => nextMemberStep("nombre")} className="flex-1">
                Atrás
              </GoberniaButton>
              <GoberniaButton
                onClick={() => nextMemberStep("familiar")}
                disabled={
                  current.role === "" ||
                  (current.role === "other" && current.role_custom.trim().length < 2)
                }
                className="flex-[2]"
                size="lg"
              >
                Continuar <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* ¿Es familiar? */}
      {memberStep === "familiar" && (
        <StepWrapper stepKey="m-familiar">
          <div className="space-y-6">
            <div className="space-y-1">
              <p className="text-xs font-semibold text-primary uppercase tracking-wide">
                {current.name}
              </p>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Pertenece a la familia propietaria?
              </h1>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {([true, false] as const).map(val => (
                <motion.button
                  key={String(val)}
                  type="button"
                  whileTap={{ scale: 0.96 }}
                  onClick={() => setCurrent(c => ({ ...c, is_family: val }))}
                  className={cn(
                    "py-4 rounded-xl border-2 text-sm font-medium transition-all duration-150",
                    current.is_family === val
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-gray-200 text-foreground hover:border-primary/40"
                  )}
                >
                  {val ? "Sí" : "No"}
                </motion.button>
              ))}
            </div>
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => nextMemberStep("rol")} className="flex-1">
                Atrás
              </GoberniaButton>
              <GoberniaButton
                onClick={() => nextMemberStep("decisiones")}
                disabled={current.is_family === null}
                className="flex-[2]"
                size="lg"
              >
                Continuar <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* ¿Toma decisiones clave? */}
      {memberStep === "decisiones" && (
        <StepWrapper stepKey="m-decisiones">
          <div className="space-y-6">
            <div className="space-y-1">
              <p className="text-xs font-semibold text-primary uppercase tracking-wide">
                {current.name}
              </p>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Toma decisiones clave en la empresa?
              </h1>
              <p className="text-sm text-muted-foreground">
                Decisiones estratégicas, financieras o de dirección.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {([true, false] as const).map(val => (
                <motion.button
                  key={String(val)}
                  type="button"
                  whileTap={{ scale: 0.96 }}
                  onClick={() => setCurrent(c => ({ ...c, makes_key_decisions: val }))}
                  className={cn(
                    "py-4 rounded-xl border-2 text-sm font-medium transition-all duration-150",
                    current.makes_key_decisions === val
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-gray-200 text-foreground hover:border-primary/40"
                  )}
                >
                  {val ? "Sí" : "No"}
                </motion.button>
              ))}
            </div>
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => nextMemberStep("familiar")} className="flex-1">
                Atrás
              </GoberniaButton>
              <GoberniaButton
                onClick={() => nextMemberStep("email")}
                disabled={current.makes_key_decisions === null}
                className="flex-[2]"
                size="lg"
              >
                Continuar <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* Email (opcional) */}
      {memberStep === "email" && (
        <StepWrapper stepKey="m-email">
          <div className="space-y-6">
            <div className="space-y-1">
              <p className="text-xs font-semibold text-primary uppercase tracking-wide">
                {current.name}
              </p>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Cuál es su correo electrónico?
              </h1>
              <p className="text-sm text-muted-foreground">
                Opcional — para futuras notificaciones del consejo.
              </p>
            </div>
            <Input
              autoFocus
              type="email"
              placeholder="correo@empresa.com  (opcional)"
              value={current.email}
              onChange={e => setCurrent(c => ({ ...c, email: e.target.value }))}
              className="h-12 text-base"
              onKeyDown={e => e.key === "Enter" && finishMember()}
            />
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => nextMemberStep("decisiones")} className="flex-1">
                Atrás
              </GoberniaButton>
              <GoberniaButton
                onClick={finishMember}
                className="flex-[2]"
                size="lg"
              >
                <Check className="h-4 w-4" />
                Agregar miembro
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}
    </div>
  )
}
