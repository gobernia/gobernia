"use client"

import { useState, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { motion } from "framer-motion"
import { ChevronRight, Building2, MapPin, Calendar, Users, GitBranch, TrendingUp, Award, Heart, RefreshCw } from "lucide-react"
import ProgressBar from "@/components/onboarding/ProgressBar"
import StepWrapper from "@/components/onboarding/StepWrapper"
import GoberniaButton from "@/components/ui/GoberniaButton"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { useOnboardingStore } from "@/lib/store"
import api from "@/lib/api"
import InfoHint from "@/components/ui/InfoHint"

// ── Catálogos ─────────────────────────────────────────────
const INDUSTRIES = [
  { value: "manufacturing",         label: "Manufactura" },
  { value: "retail",                label: "Comercio / Retail" },
  { value: "professional_services", label: "Servicios profesionales" },
  { value: "health",                label: "Salud" },
  { value: "education",             label: "Educación" },
  { value: "technology",            label: "Tecnología" },
  { value: "construction",          label: "Construcción" },
  { value: "food_beverage",         label: "Alimentos y Bebidas" },
  { value: "transport_logistics",   label: "Transporte / Logística" },
  { value: "agro",                  label: "Agro / Agricultura" },
  { value: "other",                 label: "Otra" },
]

const YEARS_OPERATING = [
  { value: "0-3",  label: "Menos de 3 años" },
  { value: "4-10", label: "4 – 10 años" },
  { value: "10-25",label: "10 – 25 años" },
  { value: "25+",  label: "Más de 25 años" },
]

const EMPLOYEES = [
  { value: "1-10",  label: "1 – 10 personas" },
  { value: "11-50", label: "11 – 50 personas" },
  { value: "51-200",label: "51 – 200 personas" },
  { value: "200+",  label: "Más de 200 personas" },
]

const BRANCHES = [
  { value: "single", label: "Solo una sede" },
  { value: "2-5",    label: "2 – 5 sedes" },
  { value: "6+",     label: "6 o más sedes" },
]

const REVENUES = [
  { value: "<1M",   label: "Menos de $1M MXN / año" },
  { value: "1M-5M", label: "$1M – $5M MXN / año" },
  { value: "5M-15M",label: "$5M – $15M MXN / año" },
  { value: "15M+",  label: "Más de $15M MXN / año" },
]

const BOARD_STATUS = [
  { value: "yes",         label: "Sí, tenemos consejo activo" },
  { value: "in_progress", label: "Estamos formándolo" },
  { value: "no",          label: "No tenemos consejo aún" },
]

const FAMILY_GENERATIONS = [
  { value: "1st",  label: "Primera generación (fundadores)" },
  { value: "2nd",  label: "Segunda generación" },
  { value: "3rd+", label: "Tercera generación o más" },
]

// ── Sub-pasos ─────────────────────────────────────────────
type SubStep =
  | "nombre"
  | "ubicacion"
  | "industria"
  | "antiguedad"
  | "empleados"
  | "sucursales"
  | "ingresos"
  | "consejo"
  | "familiar"
  | "generacion"
  | "protocolo"

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

function YesNoCard({
  value, selected, onClick,
}: { value: boolean; selected: boolean; onClick: () => void }) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.96 }}
      onClick={onClick}
      className={cn(
        "py-4 rounded-xl border-2 text-sm font-medium transition-all duration-150",
        selected
          ? "border-primary bg-primary/5 text-primary"
          : "border-gray-200 text-foreground hover:border-primary/40"
      )}
    >
      {value ? "Sí" : "No"}
    </motion.button>
  )
}

export default function Etapa1Page() {
  const router = useRouter()
  const fromDatos = useSearchParams().get("from") === "datos"
  const { sessionId, setSessionId, markStageComplete } = useOnboardingStore()
  const [subStep, setSubStep] = useState<SubStep>("nombre")
  const [form, setForm] = useState({
    company_name: "",
    location_city: "",
    location_state: "",
    location_country: "México",
    industry: "",
    industry_custom: "",
    years_operating: "",
    employees: "",
    branches: "",
    annual_revenue: "",
    has_board: "",
    is_family_business: null as boolean | null,
    family_generation: "",
    has_family_protocol: null as boolean | null,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Create session if it doesn't exist yet, or pre-populate from existing data
  useEffect(() => {
    if (!sessionId) {
      api.post("/onboarding/session")
        .then(r => setSessionId(r.data.session_id))
        .catch(() => {/* session will be created on submit fallback */})
      return
    }
    // Pre-populate form from existing memory_buffer (edit mode)
    api.get(`/onboarding/session/${sessionId}`).then(r => {
      const c = r.data.memory_buffer?.company
      if (!c?.name) return
      setForm(f => ({
        ...f,
        company_name:        c.name ?? "",
        location_city:       c.location?.city ?? "",
        location_state:      c.location?.state ?? "",
        location_country:    c.location?.country ?? "México",
        industry:            c.industry ?? "",
        industry_custom:     c.industry_custom ?? "",
        years_operating:     c.years_operating ?? "",
        employees:           c.employees ?? "",
        branches:            c.branches ?? "",
        annual_revenue:      c.annual_revenue ?? "",
        has_board:           c.has_board ?? "",
        is_family_business:  c.is_family_business ?? null,
        family_generation:   c.family_generation ?? "",
        has_family_protocol: c.has_family_protocol ?? null,
      }))
    }).catch(() => {})
  }, [sessionId, setSessionId])

  const next = (to: SubStep) => { setError(null); setSubStep(to) }
  const back = (to: SubStep) => { setError(null); setSubStep(to) }

  // Continue validators
  const canNombre    = form.company_name.trim().length >= 2
  const canUbicacion = form.location_city.trim().length >= 2 && form.location_state.trim().length >= 2
  const canIndustria = form.industry !== "" && (form.industry !== "other" || form.industry_custom.trim().length >= 2)
  const canAntiguedad = form.years_operating !== ""
  const canEmpleados  = form.employees !== ""
  const canSucursales = form.branches !== ""
  const canIngresos   = form.annual_revenue !== ""
  const canConsejo    = form.has_board !== ""
  const canFamiliar   = form.is_family_business !== null
  const canGeneracion = form.family_generation !== ""
  const canProtocolo  = form.has_family_protocol !== null

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    try {
      let sid = sessionId
      if (!sid) {
        const r = await api.post("/onboarding/session")
        sid = r.data.session_id
        setSessionId(sid!)
      }
      const payload = {
        company_name:        form.company_name.trim(),
        industry:            form.industry,
        industry_custom:     form.industry === "other" ? form.industry_custom.trim() : undefined,
        location_city:       form.location_city.trim(),
        location_state:      form.location_state.trim(),
        location_country:    form.location_country,
        years_operating:     form.years_operating,
        employees:           form.employees,
        annual_revenue:      form.annual_revenue,
        branches:            form.branches,
        is_family_business:  form.is_family_business,
        family_generation:   form.is_family_business ? form.family_generation : undefined,
        has_family_protocol: form.is_family_business ? form.has_family_protocol : undefined,
        has_board:           form.has_board,
      }

      try {
        await api.post(`/onboarding/${sid}/etapa-1`, payload)
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } })?.response?.status
        if (status === 404) {
          // Sesión corrupta/antigua — crear nueva y reintentar
          const r = await api.post("/onboarding/session")
          sid = r.data.session_id
          setSessionId(sid!)
          await api.post(`/onboarding/${sid}/etapa-1`, payload)
        } else {
          throw err
        }
      }

      markStageComplete(1)
      router.push(fromDatos ? "/dashboard/datos" : "/onboarding/etapa-2")
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? "Ocurrió un error. Intenta de nuevo.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-xl 3xl:max-w-2xl space-y-8">
      <ProgressBar currentStep={1} />

      {/* ── Nombre ── */}
      {subStep === "nombre" && (
        <StepWrapper stepKey="nombre">
          <div className="space-y-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-primary mb-3">
                <Building2 className="h-5 w-5" />
                <span className="text-sm font-medium">Empecemos</span>
              </div>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Cómo se llama tu empresa?
              </h1>
              <p className="text-sm text-muted-foreground">
                Así identificaremos tu espacio en Gobernia.
              </p>
            </div>
            <Input
              autoFocus
              placeholder="Ej. Grupo Martínez SA de CV"
              value={form.company_name}
              onChange={e => setForm(f => ({ ...f, company_name: e.target.value }))}
              className="h-12 text-base"
              onKeyDown={e => e.key === "Enter" && canNombre && next("ubicacion")}
            />
            <GoberniaButton
              onClick={() => next("ubicacion")}
              disabled={!canNombre}
              className="w-full"
              size="lg"
            >
              Continuar <ChevronRight className="h-4 w-4" />
            </GoberniaButton>
          </div>
        </StepWrapper>
      )}

      {/* ── Ubicación ── */}
      {subStep === "ubicacion" && (
        <StepWrapper stepKey="ubicacion">
          <div className="space-y-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-primary mb-3">
                <MapPin className="h-5 w-5" />
                <span className="text-sm font-medium">Ubicación</span>
              </div>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Dónde opera{" "}
                <span className="text-primary">{form.company_name}</span>?
              </h1>
              <p className="text-sm text-muted-foreground">
                Ciudad y estado / provincia de la sede principal.
              </p>
            </div>
            <div className="space-y-3">
              <Input
                autoFocus
                placeholder="Ciudad  (ej. Monterrey)"
                value={form.location_city}
                onChange={e => setForm(f => ({ ...f, location_city: e.target.value }))}
                className="h-12 text-base"
              />
              <Input
                placeholder="Estado  (ej. Nuevo León)"
                value={form.location_state}
                onChange={e => setForm(f => ({ ...f, location_state: e.target.value }))}
                className="h-12 text-base"
                onKeyDown={e => e.key === "Enter" && canUbicacion && next("industria")}
              />
            </div>
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => back("nombre")} className="flex-1">
                Atrás
              </GoberniaButton>
              <GoberniaButton
                onClick={() => next("industria")}
                disabled={!canUbicacion}
                className="flex-[2]"
                size="lg"
              >
                Continuar <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* ── Industria ── */}
      {subStep === "industria" && (
        <StepWrapper stepKey="industria">
          <div className="space-y-6">
            <div className="space-y-1">
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿En qué industria opera?
              </h1>
              <p className="text-sm text-muted-foreground">
                Esto personaliza los KPIs y métricas de tu consejo.
              </p>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {INDUSTRIES.map(opt => (
                <OptionCard
                  key={opt.value}
                  selected={form.industry === opt.value}
                  onClick={() => setForm(f => ({ ...f, industry: opt.value }))}
                  label={opt.label}
                />
              ))}
            </div>
            {form.industry === "other" && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}>
                <Input
                  autoFocus
                  placeholder="Describe tu industria"
                  value={form.industry_custom}
                  onChange={e => setForm(f => ({ ...f, industry_custom: e.target.value }))}
                  className="h-11"
                />
              </motion.div>
            )}
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => back("ubicacion")} className="flex-1">
                Atrás
              </GoberniaButton>
              <GoberniaButton
                onClick={() => next("antiguedad")}
                disabled={!canIndustria}
                className="flex-[2]"
                size="lg"
              >
                Continuar <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* ── Antigüedad ── */}
      {subStep === "antiguedad" && (
        <StepWrapper stepKey="antiguedad">
          <div className="space-y-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-primary mb-3">
                <Calendar className="h-5 w-5" />
                <span className="text-sm font-medium">Trayectoria</span>
              </div>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Cuántos años lleva operando la empresa?
              </h1>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {YEARS_OPERATING.map(opt => (
                <OptionCard
                  key={opt.value}
                  selected={form.years_operating === opt.value}
                  onClick={() => setForm(f => ({ ...f, years_operating: opt.value }))}
                  label={opt.label}
                />
              ))}
            </div>
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => back("industria")} className="flex-1">
                Atrás
              </GoberniaButton>
              <GoberniaButton
                onClick={() => next("empleados")}
                disabled={!canAntiguedad}
                className="flex-[2]"
                size="lg"
              >
                Continuar <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* ── Empleados ── */}
      {subStep === "empleados" && (
        <StepWrapper stepKey="empleados">
          <div className="space-y-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-primary mb-3">
                <Users className="h-5 w-5" />
                <span className="text-sm font-medium">Tamaño</span>
              </div>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Cuántas personas trabajan en la empresa?
              </h1>
              <p className="text-sm text-muted-foreground">
                Ayuda a calibrar los benchmarks de tu industria.
              </p>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {EMPLOYEES.map(opt => (
                <OptionCard
                  key={opt.value}
                  selected={form.employees === opt.value}
                  onClick={() => setForm(f => ({ ...f, employees: opt.value }))}
                  label={opt.label}
                />
              ))}
            </div>
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => back("antiguedad")} className="flex-1">
                Atrás
              </GoberniaButton>
              <GoberniaButton
                onClick={() => next("sucursales")}
                disabled={!canEmpleados}
                className="flex-[2]"
                size="lg"
              >
                Continuar <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* ── Sucursales ── */}
      {subStep === "sucursales" && (
        <StepWrapper stepKey="sucursales">
          <div className="space-y-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-primary mb-3">
                <GitBranch className="h-5 w-5" />
                <span className="text-sm font-medium">Presencia</span>
              </div>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Cuántas sedes o sucursales tienen?
              </h1>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {BRANCHES.map(opt => (
                <OptionCard
                  key={opt.value}
                  selected={form.branches === opt.value}
                  onClick={() => setForm(f => ({ ...f, branches: opt.value }))}
                  label={opt.label}
                />
              ))}
            </div>
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => back("empleados")} className="flex-1">
                Atrás
              </GoberniaButton>
              <GoberniaButton
                onClick={() => next("ingresos")}
                disabled={!canSucursales}
                className="flex-[2]"
                size="lg"
              >
                Continuar <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* ── Ingresos ── */}
      {subStep === "ingresos" && (
        <StepWrapper stepKey="ingresos">
          <div className="space-y-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-primary mb-3">
                <TrendingUp className="h-5 w-5" />
                <span className="text-sm font-medium">Escala</span>
              </div>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Cuál es el rango de ingresos anuales?
              </h1>
              <p className="text-sm text-muted-foreground">
                Confidencial — solo la usan tus agentes para calibrar análisis.
              </p>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {REVENUES.map(opt => (
                <OptionCard
                  key={opt.value}
                  selected={form.annual_revenue === opt.value}
                  onClick={() => setForm(f => ({ ...f, annual_revenue: opt.value }))}
                  label={opt.label}
                />
              ))}
            </div>
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => back("sucursales")} className="flex-1">
                Atrás
              </GoberniaButton>
              <GoberniaButton
                onClick={() => next("consejo")}
                disabled={!canIngresos}
                className="flex-[2]"
                size="lg"
              >
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
              <div className="flex items-center gap-2 text-primary mb-3">
                <Award className="h-5 w-5" />
                <span className="text-sm font-medium">Gobierno</span>
              </div>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿La empresa tiene un consejo de administración? <InfoHint text="Órgano que reúne a directivos y consejeros para decidir la estrategia y supervisar a la dirección." />
              </h1>
              <p className="text-sm text-muted-foreground">
                Gobernia puede ayudarte a estructurarlo si aún no lo tienen.
              </p>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {BOARD_STATUS.map(opt => (
                <OptionCard
                  key={opt.value}
                  selected={form.has_board === opt.value}
                  onClick={() => setForm(f => ({ ...f, has_board: opt.value }))}
                  label={opt.label}
                />
              ))}
            </div>
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => back("ingresos")} className="flex-1">
                Atrás
              </GoberniaButton>
              <GoberniaButton
                onClick={() => next("familiar")}
                disabled={!canConsejo}
                className="flex-[2]"
                size="lg"
              >
                Continuar <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* ── Empresa familiar ── */}
      {subStep === "familiar" && (
        <StepWrapper stepKey="familiar">
          <div className="space-y-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-primary mb-3">
                <Heart className="h-5 w-5" />
                <span className="text-sm font-medium">Estructura</span>
              </div>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Es una empresa familiar? <InfoHint text="Empresa cuya propiedad y/o dirección está en manos de una familia." />
              </h1>
              <p className="text-sm text-muted-foreground">
                Activa módulos de protocolo y sucesión si es el caso.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {([true, false] as const).map(val => (
                <motion.button
                  key={String(val)}
                  type="button"
                  whileTap={{ scale: 0.96 }}
                  onClick={() => setForm(f => ({ ...f, is_family_business: val }))}
                  className={cn(
                    "py-4 rounded-xl border-2 text-sm font-medium transition-all duration-150",
                    form.is_family_business === val
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-gray-200 text-foreground hover:border-primary/40"
                  )}
                >
                  {val ? "Sí, es familiar" : "No"}
                </motion.button>
              ))}
            </div>
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => back("consejo")} className="flex-1">
                Atrás
              </GoberniaButton>
              <GoberniaButton
                onClick={() => {
                  if (form.is_family_business) next("generacion")
                  else handleSubmit()
                }}
                disabled={!canFamiliar}
                loading={loading && form.is_family_business === false}
                className="flex-[2]"
                size="lg"
              >
                {form.is_family_business ? (
                  <>Continuar <ChevronRight className="h-4 w-4" /></>
                ) : (
                  <>Guardar y continuar <ChevronRight className="h-4 w-4" /></>
                )}
              </GoberniaButton>
            </div>
            {error && <p className="text-sm text-red-500 text-center">{error}</p>}
          </div>
        </StepWrapper>
      )}

      {/* ── Generación familiar ── */}
      {subStep === "generacion" && (
        <StepWrapper stepKey="generacion">
          <div className="space-y-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-primary mb-3">
                <RefreshCw className="h-5 w-5" />
                <span className="text-sm font-medium">Historia familiar</span>
              </div>
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿En qué generación está la empresa? <InfoHint text="Qué generación dirige hoy la empresa: 1ª = fundadores, 2ª = hijos, 3ª = nietos, etc." />
              </h1>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {FAMILY_GENERATIONS.map(opt => (
                <OptionCard
                  key={opt.value}
                  selected={form.family_generation === opt.value}
                  onClick={() => setForm(f => ({ ...f, family_generation: opt.value }))}
                  label={opt.label}
                />
              ))}
            </div>
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => back("familiar")} className="flex-1">
                Atrás
              </GoberniaButton>
              <GoberniaButton
                onClick={() => next("protocolo")}
                disabled={!canGeneracion}
                className="flex-[2]"
                size="lg"
              >
                Continuar <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* ── Protocolo familiar ── */}
      {subStep === "protocolo" && (
        <StepWrapper stepKey="protocolo">
          <div className="space-y-6">
            <div className="space-y-1">
              <h1 className="text-2xl font-bold text-foreground leading-tight">
                ¿Tienen un protocolo familiar o acuerdo de accionistas? <InfoHint text="Acuerdo que fija las reglas de la familia sobre la empresa: sucesión, entrada de familiares, reparto y manejo de conflictos." />
              </h1>
              <p className="text-sm text-muted-foreground">
                No te preocupes si no — podemos ayudarte a estructurarlo.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {([true, false] as const).map(val => (
                <motion.button
                  key={String(val)}
                  type="button"
                  whileTap={{ scale: 0.96 }}
                  onClick={() => setForm(f => ({ ...f, has_family_protocol: val }))}
                  className={cn(
                    "py-4 rounded-xl border-2 text-sm font-medium transition-all duration-150",
                    form.has_family_protocol === val
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-gray-200 text-foreground hover:border-primary/40"
                  )}
                >
                  {val ? "Sí, lo tenemos" : "No todavía"}
                </motion.button>
              ))}
            </div>
            <div className="flex gap-3">
              <GoberniaButton variant="ghost" onClick={() => back("generacion")} className="flex-1">
                Atrás
              </GoberniaButton>
              <GoberniaButton
                onClick={handleSubmit}
                disabled={!canProtocolo}
                loading={loading}
                className="flex-[2]"
                size="lg"
              >
                Guardar y continuar <ChevronRight className="h-4 w-4" />
              </GoberniaButton>
            </div>
            {error && <p className="text-sm text-red-500 text-center">{error}</p>}
          </div>
        </StepWrapper>
      )}
    </div>
  )
}
