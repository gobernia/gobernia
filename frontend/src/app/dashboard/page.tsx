"use client"

import { useState, useEffect, useRef, type CSSProperties, type ReactNode } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import Link from "next/link"
import {
  ArrowRight, Play, ChevronRight, ChevronDown,
  CheckCircle2, ArrowUpRight, X, Loader2, Pencil,
  Sparkles, FileSearch, LayoutGrid, MessagesSquare, ClipboardList, Library, Users,
  Cpu, Building2, ShieldCheck, Workflow,
} from "lucide-react"
import GoberniaLogo from "@/components/ui/GoberniaLogo"

// Una tarea de una ficha de prioridad (bento): número leading-zero, se muestra
// recortada a 2 líneas y, SI no cabe, ofrece un "Ver más" con chevron (no un "…"
// mudo). `dark` ajusta los colores cuando la ficha va sobre fondo oscuro.
function TareaItem({ n, texto, dark = false }: { n: number; texto: string; dark?: boolean }) {
  const [abierta, setAbierta] = useState(false)
  const [truncada, setTruncada] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    setTruncada(el.scrollHeight > el.clientHeight + 1)
  }, [texto])

  const num = String(n).padStart(2, "0")

  return (
    <li>
      <button
        type="button"
        onClick={() => setAbierta(o => !o)}
        aria-expanded={abierta}
        className={`flex w-full gap-2.5 text-left rounded-md -mx-1 px-1 py-1 transition-colors focus-visible:outline-none ${
          dark ? "hover:bg-white/[0.06]" : "hover:bg-black/[0.04]"
        }`}
        title={abierta ? "Contraer" : "Leer completa"}
      >
        <span
          className="shrink-0 pt-0.5 text-[11px] font-extrabold tabular-nums"
          style={{ color: dark ? "rgba(255,255,255,.5)" : MUTED }}
        >
          {num}
        </span>
        <span className="flex min-w-0 flex-1 flex-col items-start gap-1">
          <span
            ref={ref}
            className={`text-[14.5px] leading-snug ${abierta ? "" : "line-clamp-2"}`}
            style={{ color: dark ? "#fff" : INK }}
          >
            {texto}
          </span>
          {(truncada || abierta) && (
            <span
              className="inline-flex items-center gap-0.5 text-[10px] font-bold uppercase tracking-wide"
              style={{ color: ACCENT }}
            >
              {abierta ? "Ver menos" : "Ver más"}
              <ChevronDown className={`h-3 w-3 transition-transform ${abierta ? "rotate-180" : ""}`} />
            </span>
          )}
        </span>
      </button>
    </li>
  )
}
import SecretarioWelcome from "@/components/dashboard/SecretarioWelcome"
import { PageShell } from "@/components/ui/PageShell"
import { supabase } from "@/lib/supabase"
import { useOnboardingStore } from "@/lib/store"
import api from "@/lib/api"
import { getLogo } from "@/lib/logo"
import { getRoadmap, type Roadmap, type Pilar } from "@/lib/roadmap"
import { roadmapIsEmpty } from "@/components/roadmap/shared"

// ── Easing ────────────────────────────────────────────────
type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

// ── Data ──────────────────────────────────────────────────
const ETAPAS = [
  { n: 1, label: "Empresa" },
  { n: 2, label: "Equipo" },
  { n: 3, label: "Prioridades" },
  { n: 4, label: "Diagnóstico" },
  { n: 5, label: "Indicadores" },
  { n: 6, label: "Gobierno" },
  { n: 7, label: "Documentos" },
  { n: 8, label: "Visión" },
]

const MONTH_NAMES = [
  "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

// El flujo del producto, en el mismo orden que la barra lateral.
// Es el acceso principal desde Inicio: una rejilla, no una lista suelta.
const FLUJO = [
  {
    href: "/dashboard/diagnostico", icon: FileSearch, step: "01", label: "Diagnóstico",
    desc: "El estado real de tu gobierno corporativo, con evidencia.",
  },
  {
    href: "/dashboard/foda", icon: LayoutGrid, step: "02", label: "FODA",
    desc: "Fortalezas, oportunidades, debilidades y amenazas del negocio.",
  },
  {
    href: "/dashboard/perspectivas", icon: MessagesSquare, step: "03", label: "Equipo",
    desc: "Lo que ven tu equipo, tus socios y tus clientes desde fuera.",
  },
  {
    href: "/dashboard/plan", icon: ClipboardList, step: "04", label: "Roadmap",
    desc: "Prioridades, tareas e Indicadores mes a mes, generados por tu Consejo.",
  },
  {
    href: "/dashboard/biblioteca", icon: Library, step: "05", label: "Biblioteca",
    desc: "Los documentos que sostienen cada decisión del Consejo.",
  },
  {
    href: "/dashboard/consejo", icon: Users, step: "06", label: "Board IA",
    desc: "Cinco consejeros con IA: finanzas, estrategia, riesgos, auditoría y el Retador.",
  },
]

// Sesiones de consejo ocultas por ahora (no se borra el código). Cambiar a true para reactivar.
const SHOW_SESSIONS = false

// ── Types ─────────────────────────────────────────────────
interface CompanySummary {
  company_name: string
  industry: string
  governance_score?: number
  activated_modules: string[]
}

interface BoardSession {
  board_session_id: string
  period_year: number
  period_month: number
  period_label: string
  status: string
  governance_score_snapshot: number | null
  message_count: number
  created_at: string
}

// ── Helpers ───────────────────────────────────────────────
function greeting() {
  const h = new Date().getHours()
  if (h < 12) return "Buenos días"
  if (h < 19) return "Buenas tardes"
  return "Buenas noches"
}

function todayLabel() {
  return new Date().toLocaleDateString("es-MX", {
    weekday: "long", day: "numeric", month: "long",
  })
}

function statusLabel(s: string) {
  const map: Record<string, string> = {
    draft: "Borrador", active: "Activa", completed: "Completada",
  }
  return map[s] ?? s
}

// ── Sistema de diseño BENTO ───────────────────────────────
// El Inicio muestra la estrategia "de un vistazo" con estética bento: reusa la
// data del Roadmap que ya vive en /dashboard/plan. Aquí no se edita — para eso
// está "Editar mi Roadmap". Tokens por hex (Tailwind v4 no ve clases dinámicas).
const PAPER = "#F2F2F0"
const INK   = "#0E1626"
const INK2  = "#39435A"
const MUTED = "#6E7686"
const CARD  = "#FFFFFF"
const SAND  = "#E8E3D8"
const SAND2 = "#F0ECE3"
const BNAVY = "#152742"
const ACCENT = "#FF5C1A"
const LINE  = "#E2E2DC"

// Clases compartidas por todos los tiles del bento.
const TILE = "rounded-[26px] p-[30px] relative overflow-hidden"
// El CSS global pone h1/h2 en serif (Newsreader). En el bento NO queremos serif:
// forzamos sans en cada título y número display.
const SANS: CSSProperties = { fontFamily: "var(--font-sans)" }

// Anchos bento con responsive: móvil apila todo; md reparte a mitades; lg abre 4/8.
const COL = {
  c4:  "col-span-12 md:col-span-6 lg:col-span-4",
  c6:  "col-span-12 md:col-span-6",
  c8:  "col-span-12 lg:col-span-8",
  c12: "col-span-12",
}

type BG = "card" | "sand" | "sand2" | "dark" | "ink"
function bgStyle(bg: BG): CSSProperties {
  switch (bg) {
    case "sand":  return { background: SAND }
    case "sand2": return { background: SAND2 }
    case "dark":  return { background: BNAVY, color: "#fff" }
    case "ink":   return { background: INK, color: "#fff" }
    default:      return { background: CARD }
  }
}

function Eyebrow({ children, dark = false, className = "" }: { children: ReactNode; dark?: boolean; className?: string }) {
  return (
    <p
      className={`text-[10.5px] font-extrabold uppercase tracking-[0.17em] ${className}`}
      style={{ color: dark ? "rgba(255,255,255,.6)" : MUTED }}
    >
      {children}
    </p>
  )
}

// Detalle firma: subrayado a mano "squiggle" naranja bajo una palabra del hero.
function Squiggle({ children }: { children: ReactNode }) {
  return (
    <span className="relative inline-block">
      {children}
      <span
        aria-hidden
        className="absolute left-0 right-0 -bottom-1.5 h-[7px]"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='40' height='7' viewBox='0 0 40 7'><path d='M0 4 Q5 0 10 4 T20 4 T30 4 T40 4' fill='none' stroke='%23FF5C1A' stroke-width='2.2'/></svg>\")",
          backgroundRepeat: "repeat-x",
          backgroundSize: "20px 7px",
        }}
      />
    </span>
  )
}

// Número display grande del hero (peso 700, tracking negativo). `sm` = variante chica.
function DisplayNum({ value, unit, sm = false }: { value: ReactNode; unit: string; sm?: boolean }) {
  return (
    <div>
      <p
        className="font-bold tracking-[-.05em] leading-[.88]"
        style={{ ...SANS, fontSize: sm ? "clamp(40px,7vw,56px)" : "clamp(46px,9vw,82px)" }}
      >
        {value}
      </p>
      <p className="mt-2.5 max-w-[20ch] text-[14px] font-semibold leading-snug" style={{ color: INK2 }}>
        {unit}
      </p>
    </div>
  )
}

function MiniLbl({ children, dark }: { children: ReactNode; dark?: boolean }) {
  return (
    <div
      className="mb-3 text-[10px] font-extrabold uppercase tracking-[0.16em]"
      style={{ color: dark ? "rgba(255,255,255,.55)" : MUTED }}
    >
      {children}
    </div>
  )
}

// Ficha de prioridad: índice grande y tenue, nombre, propósito (2 líneas) y un
// split de dos columnas — Indicadores (bullets cuadrados naranjas) y Tareas
// (numeradas con "Ver más" expandible). `dark` cambia bordes y colores de texto.
function PrioTile({ pilar, index, bg, col }: { pilar: Pilar; index: number; bg: BG; col: string }) {
  const dark = bg === "dark" || bg === "ink"
  const kpis = (pilar.kpis ?? []).filter(k => k.label).slice(0, 5)
  const tareas = (pilar.estrategias ?? []).slice(0, 6)
  const purpose = pilar.objetivo || pilar.descripcion
  const num = String(index + 1).padStart(2, "0")
  return (
    <div id={`prioridad-${index}`} className={`${TILE} ${col} scroll-mt-24`} style={bgStyle(bg)}>
      <div className="relative">
        <div className="flex items-start gap-[18px]">
          <div className="shrink-0 font-bold leading-[.85] tracking-[-.04em]" style={{ ...SANS, fontSize: "46px", opacity: 0.22 }}>
            {num}
          </div>
          <div className="min-w-0">
            <h3 className="text-[23px] font-bold leading-tight tracking-[-.025em]" style={SANS}>
              {pilar.nombre || `Prioridad ${index + 1}`}
            </h3>
            {purpose && (
              <p className="mt-3 text-[15.5px] leading-relaxed line-clamp-2" style={{ color: dark ? "rgba(255,255,255,.86)" : INK2 }}>
                {purpose}
              </p>
            )}
          </div>
        </div>
        <div
          className="mt-6 grid grid-cols-1 gap-5 border-t pt-5 sm:grid-cols-2"
          style={{ borderColor: dark ? "rgba(255,255,255,.16)" : LINE }}
        >
          <div>
            <MiniLbl dark={dark}>Indicadores</MiniLbl>
            {kpis.length > 0 ? (
              <ul className="space-y-0.5">
                {kpis.map((k, j) => (
                  <li key={j} className="relative py-1.5 pl-[18px] text-[14.5px] leading-snug" style={{ color: dark ? "#fff" : INK }}>
                    <span className="absolute left-0 top-[13px] h-[7px] w-[7px] rounded-[2px]" style={{ background: ACCENT }} />
                    {k.label}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[13px]" style={{ color: MUTED }}>—</p>
            )}
          </div>
          <div>
            <MiniLbl dark={dark}>Tareas</MiniLbl>
            {tareas.length > 0 ? (
              <ol className="space-y-0.5">
                {tareas.map((t, j) => (
                  <TareaItem key={j} n={j + 1} texto={t} dark={dark} />
                ))}
              </ol>
            ) : (
              <p className="text-[13px]" style={{ color: MUTED }}>—</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

const ENAB_ICONS = [Users, Cpu, Building2, ShieldCheck, Workflow]

function RoadmapOnePager({
  roadmap, companyName, companyLogo,
}: { roadmap: Roadmap; companyName: string | null; companyLogo: string | null }) {
  const objetivos = (roadmap.objetivos_estrategicos ?? []).filter(Boolean)
  const enablers  = (roadmap.key_enablers ?? []).filter(Boolean)
  const pilares   = roadmap.pilares ?? []
  const totalInd  = pilares.reduce((a, p) => a + (p.kpis ?? []).filter(k => k.label).length, 0)
  const totalTar  = pilares.reduce((a, p) => a + (p.estrategias ?? []).length, 0)
  const restPilares = pilares.slice(1)

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, ease: EASE, delay: 0.2 }}
    >
      {/* 1. TOPBAR */}
      <div className="mb-1 flex items-center gap-3.5 px-1 pb-4">
        {companyLogo && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={companyLogo}
            alt={companyName ?? "Logo de tu empresa"}
            className="h-9 w-9 shrink-0 rounded-lg border border-black/5 bg-white object-contain"
          />
        )}
        <div className="leading-tight">
          <Eyebrow className="mb-0">{todayLabel()}</Eyebrow>
          <div className="text-[18px] font-bold tracking-[-.02em]" style={{ ...SANS, color: INK }}>
            {greeting()}, {companyName || "tu empresa"}.
          </div>
        </div>
        <div className="flex-1" />
        <Link
          href="/dashboard/plan"
          className="inline-flex items-center gap-2.5 whitespace-nowrap rounded-full px-5 py-3 text-[13px] font-bold tracking-wide text-white transition-colors hover:brightness-90"
          style={{ background: ACCENT }}
        >
          <span className="hidden sm:inline">Editar mi Roadmap</span>
          <span className="grid h-[22px] w-[22px] place-items-center rounded-full" style={{ background: "rgba(255,255,255,.18)" }}>
            <Pencil className="h-3 w-3" />
          </span>
        </Link>
      </div>

      {/* BENTO */}
      <div className="grid grid-cols-12 gap-4">

        {/* 2. HERO — en pastel (sand), texto oscuro, sin rayas */}
        <div className={`${TILE} ${COL.c8} flex min-h-[300px] flex-col justify-between`} style={{ background: SAND, color: INK }}>
          <div className="relative">
            <Eyebrow className="mb-3">Tu estrategia</Eyebrow>
            <h2 className="text-[34px] font-bold leading-[1.08] tracking-[-.03em]" style={SANS}>
              Roadmap<br />de un <Squiggle>vistazo</Squiggle>
            </h2>
          </div>
          <div className="relative mt-8 flex flex-wrap items-end gap-x-10 gap-y-6">
            <DisplayNum value={pilares.length} unit="Prioridades estratégicas" />
            <DisplayNum value={totalInd} unit="Indicadores" sm />
            <DisplayNum value={totalTar} unit="Tareas" sm />
          </div>
        </div>

        {/* 3. ONBOARDING — en azul (navy), texto blanco, sin líneas */}
        <div className={`${TILE} ${COL.c4} flex min-h-[274px] flex-col justify-between`} style={bgStyle("dark")}>
          <div>
            <Eyebrow dark className="mb-3">Onboarding</Eyebrow>
            <h3 className="text-[23px] font-bold leading-tight tracking-[-.025em]" style={SANS}>Completado</h3>
            <p className="mt-3.5 text-[15px] leading-relaxed" style={{ color: "rgba(255,255,255,.82)" }}>
              Tu roadmap ya está configurado y listo para consultarse.
            </p>
          </div>
          <a href="#prioridades" className="group inline-flex items-center gap-3 text-[12px] font-extrabold uppercase tracking-[0.09em]">
            Ver prioridades
            <span
              className="grid h-7 w-7 place-items-center rounded-full border text-[12px] transition-colors group-hover:border-transparent group-hover:bg-[#FF5C1A] group-hover:text-white"
              style={{ borderColor: "currentColor" }}
            >
              →
            </span>
          </a>
        </div>

        {/* 4. MISIÓN */}
        <div className={`${TILE} ${COL.c6}`} style={bgStyle("card")}>
          <Eyebrow className="mb-3">Misión</Eyebrow>
          <h3 className="text-[20px] font-semibold leading-[1.45] tracking-[-.015em]" style={SANS}>
            {roadmap.mision || "—"}
          </h3>
        </div>

        {/* 5. VISIÓN */}
        <div className={`${TILE} ${COL.c6}`} style={bgStyle("sand2")}>
          <Eyebrow className="mb-3">Visión</Eyebrow>
          <h3 className="text-[20px] font-semibold leading-[1.45] tracking-[-.015em]" style={SANS}>
            {roadmap.vision || "—"}
          </h3>
        </div>

        {/* 6. KPI VISIÓN — los compromisos */}
        {objetivos.length > 0 && (
          <>
            <div className="col-span-12 px-1 pt-3">
              <Eyebrow>KPI Visión — los compromisos</Eyebrow>
            </div>
            {objetivos.map((o, i) => (
              <div key={i} className={`${TILE} ${COL.c4} flex min-h-[170px] flex-col`} style={bgStyle(i % 2 === 0 ? "sand" : "card")}>
                <div className="text-[13px] font-extrabold tracking-[0.04em]" style={{ color: ACCENT }}>
                  {String(i + 1).padStart(2, "0")}
                </div>
                <div className="mt-3.5 text-[16px] font-semibold leading-snug tracking-[-.015em]" style={{ color: INK }}>
                  {o}
                </div>
              </div>
            ))}
          </>
        )}

        {/* 7. PRIORIDADES ESTRATÉGICAS */}
        {pilares.length > 0 && (
          <>
            <div id="prioridades" className="col-span-12 scroll-mt-24 px-1 pt-4">
              <Eyebrow>Prioridades estratégicas — cada ficha trae sus indicadores y sus tareas</Eyebrow>
            </div>

            {/* Prioridad 1 (dark, ancha) + tile de Composición (ink) al lado */}
            <PrioTile pilar={pilares[0]} index={0} bg="dark" col={COL.c8} />
            <div className={`${TILE} ${COL.c4} flex flex-col justify-between`} style={bgStyle("ink")}>
              <div>
                <Eyebrow dark className="mb-3">Composición del roadmap</Eyebrow>
                <h3 className="text-[19px] font-bold leading-tight tracking-[-.02em]" style={SANS}>
                  {pilares.length} prioridades · {totalTar} tareas en tu plan.
                </h3>
              </div>
              <div>
                <div className="mt-5 flex gap-[3px]">
                  {pilares.map((_, i) => (
                    <span
                      key={i}
                      className="grid h-11 flex-1 place-items-center rounded-[7px] text-[11px] font-extrabold"
                      style={{
                        background: i === 0 ? ACCENT : "rgba(255,255,255,.22)",
                        color: i === 0 ? "#fff" : "rgba(255,255,255,.9)",
                      }}
                    >
                      {String(i + 1).padStart(2, "0")}
                    </span>
                  ))}
                </div>
                <div className="mt-3.5 flex flex-wrap gap-x-5 gap-y-2 text-[12px] font-semibold" style={{ color: "rgba(255,255,255,.62)" }}>
                  <span>{pilares.length} prioridades</span>
                  <span>{totalInd} indicadores</span>
                  <span>{totalTar} tareas</span>
                </div>
              </div>
            </div>

            {/* Prioridades restantes: alternan sand / card, a media anchura */}
            {restPilares.map((p, i) => (
              <PrioTile key={i + 1} pilar={p} index={i + 1} bg={i % 2 === 0 ? "sand" : "card"} col={COL.c6} />
            ))}
          </>
        )}

        {/* 8. KEY ENABLERS */}
        {enablers.length > 0 && (
          <>
            <div className="col-span-12 px-1 pt-4">
              <Eyebrow>Key enablers</Eyebrow>
            </div>
            {enablers.map((e, i) => {
              const Icon = ENAB_ICONS[i % ENAB_ICONS.length]
              return (
                <div key={i} className={`${TILE} ${COL.c4} flex items-start gap-4`} style={bgStyle(i % 2 === 0 ? "card" : "sand")}>
                  <span className="grid h-12 w-12 shrink-0 place-items-center rounded-[14px] text-white" style={{ background: ACCENT }}>
                    <Icon className="h-[22px] w-[22px]" strokeWidth={1.9} />
                  </span>
                  <p className="text-[15.5px] leading-relaxed" style={{ color: INK }}>{e}</p>
                </div>
              )
            })}
          </>
        )}
      </div>

      {/* 9. Nota al pie */}
      <p className="mt-8 border-l-2 pl-4 text-[13px] leading-relaxed" style={{ color: MUTED, borderColor: LINE }}>
        Los números grandes son conteos reales de tu roadmap: {pilares.length} prioridades,{" "}
        {totalInd} indicadores y {totalTar} tareas. Toca cualquier tarea recortada para leerla completa.
      </p>
    </motion.div>
  )
}

// ── Page ──────────────────────────────────────────────────
export default function DashboardPage() {
  const router = useRouter()
  const { completedStages, hydrate, reset } = useOnboardingStore()

  const [userEmail,   setUserEmail]   = useState<string | null>(null)
  const [userName,    setUserName]    = useState<string>("")
  const [summary,     setSummary]     = useState<CompanySummary | null>(null)
  const [sessions,    setSessions]    = useState<BoardSession[]>([])
  const [sessLoading, setSessLoading] = useState(true)

  const [roadmap,     setRoadmap]     = useState<Roadmap | null>(null)
  const [roadmapChecked, setRoadmapChecked] = useState(false)

  const [showSetupModal, setShowSetupModal] = useState(false)

  // Nova sesión modal state
  const [showModal,    setShowModal]   = useState(false)
  const [modalYear,    setModalYear]   = useState(new Date().getFullYear())
  const [modalMonth,   setModalMonth]  = useState(new Date().getMonth() + 1)
  const [creating,     setCreating]    = useState(false)
  const [createError,  setCreateError] = useState<string | null>(null)
  const [companyLogo,  setCompanyLogo] = useState<string | null>(null)

  useEffect(() => {
    getLogo()
      .then(r => setCompanyLogo(r.logo))
      .catch(() => {})

    supabase.auth.getUser().then(({ data }) => {
      setUserEmail(data.user?.email ?? null)
      const meta = data.user?.user_metadata ?? {}
      const name = (meta.full_name ?? meta.name ?? "") as string
      // solo el primer nombre, para un saludo más cálido
      setUserName(name.trim().split(/\s+/)[0] ?? "")
    })

    // Siempre resolvemos la sesión del usuario ACTUAL vía /my-session (va con su token).
    // Si el backend no tiene sesión (usuario nuevo → 204), reseteamos el store para no
    // arrastrar el onboarding de un usuario anterior guardado en localStorage.
    api.get("/onboarding/my-session")
      .then(r => {
        const sid = r.data?.session_id
        if (sid) {
          hydrate(sid, r.data.completed_stages ?? [])
          api.get(`/onboarding/${sid}/summary`)
            .then(rr => setSummary(rr.data))
            .catch(() => {})
        } else {
          reset()
        }
      })
      .catch(() => {})

    api.get("/board-sessions")
      .then(r => setSessions(r.data))
      .catch(() => {})
      .finally(() => setSessLoading(false))
  }, [hydrate, reset])

  // El roadmap alimenta el one-pager del Inicio. Si aún no hay (usuario nuevo o
  // plan sin generar), el Inicio conserva las tarjetas guiadas "Del diagnóstico al plan".
  useEffect(() => {
    let alive = true
    getRoadmap()
      .then(r => { if (alive) setRoadmap(r) })
      .catch(() => {})
      .finally(() => { if (alive) setRoadmapChecked(true) })
    return () => { alive = false }
  }, [])

  const openModal = () => {
    setModalYear(new Date().getFullYear())
    setModalMonth(new Date().getMonth() + 1)
    setCreateError(null)
    setShowModal(true)
  }

  const createSession = async () => {
    setCreating(true)
    setCreateError(null)
    try {
      const r = await api.post("/board-sessions", {
        period_year: modalYear,
        period_month: modalMonth,
      })
      setShowModal(false)
      router.push(`/dashboard/sesion/${r.data.board_session_id}`)
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status
      if (status === 409) {
        // Ya existe — buscar la sesión existente y navegar a ella
        const existing = sessions.find(
          s => s.period_year === modalYear && s.period_month === modalMonth
        )
        if (existing) {
          setShowModal(false)
          router.push(`/dashboard/sesion/${existing.board_session_id}`)
          return
        }
      }
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setCreateError(msg ?? "No se pudo crear la sesión. Intenta de nuevo.")
    } finally {
      setCreating(false)
    }
  }

  const onboardingComplete = completedStages.length >= 8
  const hasRoadmap         = !!roadmap && !roadmapIsEmpty(roadmap)
  const nextEtapa          = ETAPAS.find(e => !completedStages.includes(e.n))
  const companyName        = summary?.company_name ?? null

  const tryCreateSession = () => {
    if (onboardingComplete) openModal()
    else setShowSetupModal(true)
  }

  const currentYear = new Date().getFullYear()
  const years = [currentYear - 1, currentYear, currentYear + 1]

  return (
    <div className="min-h-dvh text-black font-sans antialiased" style={{ background: PAPER }}>

      <SecretarioWelcome
        onboardingComplete={onboardingComplete}
        nextStageHref={"/onboarding/todd"}
        userKey={userEmail ?? ""}
        userName={userName}
      />

      {/* ── Navbar ───────────────────────────────────────── */}
      <header className="fixed top-0 inset-x-0 md:left-56 z-30 bg-white/90 backdrop-blur-md border-b border-gray-100">
        <PageShell className="h-14 flex items-center justify-between">
          <GoberniaLogo size={16} />

          <div className="flex items-center gap-5">
            {userEmail && (
              <span className="text-xs text-gray-400 hidden sm:block">{userEmail}</span>
            )}
          </div>
        </PageShell>
      </header>

      {/* ── Setup-required modal ─────────────────────────── */}
      <AnimatePresence>
        {showSetupModal && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
              onClick={() => setShowSetupModal(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              transition={{ duration: 0.25, ease: EASE }}
              className="fixed z-50 inset-x-4 top-1/2 -translate-y-1/2 max-w-sm mx-auto bg-white rounded-2xl shadow-xl p-8 space-y-5"
            >
              <div className="w-12 h-12 rounded-full bg-gray-50 flex items-center justify-center">
                <Sparkles className="h-5 w-5 text-black" />
              </div>
              <div className="space-y-2">
                <h2 className="text-lg font-bold text-black">Configura tu empresa primero</h2>
                <p className="text-sm text-gray-500 leading-relaxed">
                  Para que el Consejo de IA te entregue análisis útiles, necesitamos conocer
                  tu empresa: industria, equipo, prioridades, Indicadores y gobierno. Toma unos minutos
                  y solo se hace una vez. Después podrás iniciar sesiones cuando quieras.
                </p>
              </div>
              {!onboardingComplete && completedStages.length > 0 && (
                <div className="bg-gray-50 rounded-xl p-3">
                  <p className="text-xs text-gray-500">
                    Vas en {completedStages.length} de 8 etapas
                    {nextEtapa && ` · siguiente: ${nextEtapa.label}`}
                  </p>
                </div>
              )}
              <div className="flex gap-2">
                <button
                  onClick={() => setShowSetupModal(false)}
                  className="flex-1 text-sm font-medium text-gray-500 hover:text-[var(--gob-navy)] transition-colors"
                >
                  Más tarde
                </button>
                <Link
                  href={"/onboarding/todd"}
                  className="flex-[2] inline-flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors"
                >
                  {completedStages.length > 0 ? "Continuar configuración" : "Empezar"}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ── Nueva sesión modal ───────────────────────────── */}
      <AnimatePresence>
        {showModal && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
              onClick={() => setShowModal(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              transition={{ duration: 0.25, ease: EASE }}
              className="fixed z-50 inset-x-4 top-1/2 -translate-y-1/2 max-w-sm mx-auto bg-white rounded-2xl shadow-xl p-8 space-y-6"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-bold text-black">Nueva sesión de Consejo</h2>
                  <p className="text-xs text-gray-400 mt-0.5">Selecciona el periodo a analizar</p>
                </div>
                <button
                  onClick={() => setShowModal(false)}
                  className="text-gray-400 hover:text-[var(--gob-navy)] transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Month selector */}
              <div className="space-y-2">
                <p className="text-xs font-medium text-gray-600">Mes</p>
                <div className="grid grid-cols-4 gap-1.5">
                  {MONTH_NAMES.slice(1).map((m, i) => (
                    <button
                      key={i + 1}
                      onClick={() => setModalMonth(i + 1)}
                      className={`py-2 rounded-lg text-xs font-medium border-2 transition-all duration-100 ${
                        modalMonth === i + 1
                          ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                          : "border-gray-100 text-gray-500 hover:border-gray-300"
                      }`}
                    >
                      {m.slice(0, 3)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Year selector */}
              <div className="space-y-2">
                <p className="text-xs font-medium text-gray-600">Año</p>
                <div className="flex gap-2">
                  {years.map(y => (
                    <button
                      key={y}
                      onClick={() => setModalYear(y)}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium border-2 transition-all duration-100 ${
                        modalYear === y
                          ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                          : "border-gray-100 text-gray-500 hover:border-gray-300"
                      }`}
                    >
                      {y}
                    </button>
                  ))}
                </div>
              </div>

              {createError && (
                <p className="text-xs text-red-500">{createError}</p>
              )}

              <button
                onClick={createSession}
                disabled={creating}
                className="w-full flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-50"
              >
                {creating
                  ? <><Loader2 className="h-4 w-4 animate-spin" /> Creando…</>
                  : <>Crear sesión de {MONTH_NAMES[modalMonth]} {modalYear} <ArrowRight className="h-4 w-4" /></>
                }
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <main className="pt-14">
        <PageShell className="py-12 space-y-14">

          {/* ── Greeting ─────────────────────────────────
              Con roadmap, el saludo vive dentro del bento (topbar); aquí solo
              aparece en el estado guiado (sin roadmap). */}
          {!hasRoadmap && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: EASE }}
            className="space-y-1"
          >
            <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">
              {todayLabel()}
            </p>
            <div className="flex items-center gap-3">
              {companyLogo && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={companyLogo}
                  alt={companyName ?? "Logo de tu empresa"}
                  className="h-9 w-9 rounded-lg object-contain bg-white border border-gray-100 shrink-0"
                />
              )}
              <h1 className="text-3xl font-bold text-black tracking-tight">
                {greeting()}{companyName ? `, ${companyName}` : ""}.
              </h1>
            </div>
            {!onboardingComplete && (
              <p className="italic font-light text-sm text-gray-500 mt-1">
                {completedStages.length === 0
                  ? "Bienvenido a Gobernia. Configura tu empresa cuando estés listo."
                  : "Completa la configuración para activar tu Consejo de IA."}
              </p>
            )}
          </motion.div>
          )}

          {/* ── Onboarding banner ────────────────────────── */}
          {!onboardingComplete && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: EASE, delay: 0.1 }}
              className="border border-gray-200 rounded-2xl p-6 flex flex-col sm:flex-row sm:items-center gap-5"
            >
              <div className="flex-1 space-y-3">
                <p className="text-sm font-medium text-black">
                  {completedStages.length === 0
                    ? "Configura tu empresa para activar el Consejo"
                    : `Configuración en progreso — ${completedStages.length} de 8 etapas`}
                </p>
                <div className="flex gap-1">
                  {ETAPAS.map(e => (
                    <div
                      key={e.n}
                      title={e.label}
                      className={`h-1.5 flex-1 rounded-full transition-colors duration-300 ${
                        completedStages.includes(e.n) ? "bg-[var(--gob-navy)]" : "bg-gray-100"
                      }`}
                    />
                  ))}
                </div>
                <p className="text-xs text-gray-400">
                  {completedStages.length === 0
                    ? "Toma unos minutos. Se hace una vez y puedes editarla después."
                    : nextEtapa && `Siguiente: Etapa ${nextEtapa.n} — ${nextEtapa.label}`}
                </p>
              </div>
              <Link
                href={"/onboarding/todd"}
                className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-5 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors whitespace-nowrap"
              >
                {completedStages.length === 0 ? "Empezar configuración" : "Continuar"}
                <ArrowRight className="h-4 w-4" />
              </Link>
            </motion.div>
          )}

          {/* ── Estatus compacto (onboarding + gobernanza) ───
              Con roadmap se omite: el bento ya trae su tile de Onboarding. */}
          {onboardingComplete && !hasRoadmap && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: EASE, delay: 0.1 }}
              className="flex items-center gap-x-2 gap-y-1 flex-wrap text-xs text-gray-500"
            >
              <span className="inline-flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-[var(--gob-navy)]" />
                Onboarding: <span className="font-medium text-black">Completado</span>
              </span>
            </motion.div>
          )}

          {/* ── El Inicio como one-pager ─────────────────────
              Con roadmap → estrategia de un vistazo (solo lectura).
              Sin roadmap → el camino guiado "Del diagnóstico al plan". */}
          {hasRoadmap ? (
            <RoadmapOnePager roadmap={roadmap!} companyName={companyName} companyLogo={companyLogo} />
          ) : (!roadmapChecked && onboardingComplete) ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-5 w-5 animate-spin text-gray-300" />
            </div>
          ) : (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: EASE, delay: 0.3 }}
            className="space-y-6"
          >
            <div>
              <p className="text-xs font-medium tracking-widest text-gray-400 uppercase mb-1">
                Tu flujo
              </p>
              <h2 className="text-2xl font-bold text-black tracking-tight">
                Del diagnóstico al plan
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {FLUJO.map((f, i) => {
                const Icon = f.icon
                return (
                  <motion.div
                    key={f.href}
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, ease: EASE, delay: 0.35 + i * 0.05 }}
                  >
                    <Link
                      href={f.href}
                      className="group h-full flex flex-col border border-gray-100 rounded-2xl p-6 hover:border-gray-300 hover:shadow-sm transition-all duration-200"
                    >
                      <div className="flex items-start justify-between">
                        <span className="h-9 w-9 rounded-xl border border-gray-100 flex items-center justify-center text-[var(--gob-navy)] group-hover:border-gray-300 transition-colors">
                          <Icon className="h-4 w-4" />
                        </span>
                        <span className="text-[10px] font-medium tracking-widest text-gray-300 tabular-nums">
                          {f.step}
                        </span>
                      </div>
                      <p className="text-sm font-bold text-black mt-4">{f.label}</p>
                      <p className="text-xs text-gray-500 leading-relaxed mt-1.5 flex-1">
                        {f.desc}
                      </p>
                      <span className="mt-4 inline-flex items-center gap-1.5 text-xs font-medium text-gray-400 group-hover:text-[var(--gob-navy)] transition-colors">
                        Abrir
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      </span>
                    </Link>
                  </motion.div>
                )
              })}
            </div>
          </motion.div>
          )}

          {/* ── Board sessions ── OCULTO por ahora (no se borra; las "Sesiones de consejo" se deshabilitan temporalmente). El modal "Nueva sesión" queda en el código pero ya no es alcanzable. ── */}
          {SHOW_SESSIONS && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: EASE, delay: 0.35 }}
            className="space-y-6"
          >
            <div className="flex items-end justify-between">
              <div>
                <p className="text-xs font-medium tracking-widest text-gray-400 uppercase mb-1">Historial</p>
                <h2 className="text-2xl font-bold text-black tracking-tight">Sesiones de Consejo</h2>
              </div>
              <button
                onClick={tryCreateSession}
                className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-medium px-4 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors"
              >
                Nueva sesión <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Sessions list or empty state */}
            {sessLoading ? (
              <div className="border border-gray-100 rounded-2xl p-12 flex items-center justify-center">
                <Loader2 className="h-5 w-5 animate-spin text-gray-300" />
              </div>
            ) : sessions.length > 0 ? (
              <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-3">
                {sessions.map((s, i) => (
                  <motion.div
                    key={s.board_session_id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.35, ease: EASE, delay: i * 0.05 }}
                  >
                    <Link
                      href={`/dashboard/sesion/${s.board_session_id}`}
                      className="group flex items-center justify-between px-6 py-4 border border-gray-100 hover:border-gray-300 rounded-2xl transition-all duration-200 hover:shadow-sm"
                    >
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-xl border-2 border-gray-100 flex items-center justify-center group-hover:border-gray-300 transition-colors">
                          <span className="text-xs font-bold text-gray-400">
                            {MONTH_NAMES[s.period_month]?.slice(0, 3)}
                          </span>
                        </div>
                        <div>
                          <p className="text-sm font-medium text-black">{s.period_label}</p>
                          <p className="text-xs text-gray-400 mt-0.5">
                            {statusLabel(s.status)}
                            {s.message_count > 0 && ` · ${s.message_count} mensajes`}
                            {s.governance_score_snapshot !== null && ` · Score ${s.governance_score_snapshot}`}
                          </p>
                        </div>
                      </div>
                      <ArrowUpRight className="h-4 w-4 text-gray-300 group-hover:text-gray-500 transition-colors" />
                    </Link>
                  </motion.div>
                ))}
              </div>
            ) : (
              /* Empty state */
              <div className="border border-gray-100 rounded-2xl p-14 flex flex-col items-center justify-center text-center space-y-4">
                <div className="w-12 h-12 rounded-full border-2 border-gray-100 flex items-center justify-center">
                  <Play className="h-5 w-5 text-gray-200" />
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-medium text-black">
                    {onboardingComplete ? "Aún no hay sesiones" : "Completa el onboarding primero"}
                  </p>
                  <p className="text-xs text-gray-400 max-w-xs leading-relaxed">
                    {onboardingComplete
                      ? "Inicia tu primera sesión de Consejo para generar el diagnóstico completo de tu empresa."
                      : "Una vez que configures tu empresa, tus consejeros con IA generarán el primer análisis de gobierno."}
                  </p>
                </div>
                {onboardingComplete && (
                  <button
                    onClick={openModal}
                    className="inline-flex items-center gap-2 border border-gray-200 text-xs font-medium text-gray-700 px-4 py-2.5 rounded-xl hover:border-gray-400 hover:text-[var(--gob-navy)] transition-all duration-150 mt-1"
                  >
                    Iniciar primera sesión <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            )}
          </motion.div>
          )}

        </PageShell>
      </main>

      {/* ── Footer ───────────────────────────────────────── */}
      <footer className="border-t border-gray-100 py-6 mt-4">
        <PageShell className="flex items-center justify-between gap-4 flex-wrap text-xs text-gray-400">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-[var(--gob-navy)] flex items-center justify-center">
              <span className="text-[var(--gob-bone)] text-[8px] font-black">G</span>
            </div>
            <span>Gobernia © {new Date().getFullYear()}</span>
          </div>
          <span>Tu información está cifrada y protegida.</span>
        </PageShell>
      </footer>

    </div>
  )
}
