"use client"

// INICIO BETA — hub de resumen vivo, para comparar contra el Inicio actual.
// La idea: al entrar ves de un vistazo lo que está pasando y a dónde ir.
//   · Todd te recibe y pregunta en qué te puede ayudar (abre su panel).
//   · Última minuta: el acta de la sesión más reciente, descargable.
//   · Acciones de este mes: las tareas del mes en curso con su estado real.
//   · Accesos con resumen: espejo de las secciones del menú, cada una con
//     su estado vivo (diagnóstico, prioridades, plan, tareas, biblioteca).
// Cuando el cliente apruebe, este archivo sustituye a dashboard/page.tsx.

import { useEffect, useState, type CSSProperties, type ReactNode } from "react"
import Link from "next/link"
import {
  ArrowRight, ArrowUpRight, Loader2, FileText, MessageSquare,
  CheckCircle2, CircleDot, Circle, FileSearch, Map, CalendarCheck, Users, Library,
} from "lucide-react"
import { PageShell } from "@/components/ui/PageShell"
import { supabase } from "@/lib/supabase"
import api from "@/lib/api"
import { getBoard, downloadSesionActaPdf, type BoardMes } from "@/lib/board"
import { getRoadmap, type Roadmap } from "@/lib/roadmap"
import { getPlanAnual, type PlanAnual } from "@/lib/planAnual"

// ── Paleta bento — mismos tokens del Inicio ───────────────
const PAPER = "#F2F2F0"
const INK   = "#0E1626"
const INK2  = "#39435A"
const MUTED = "#6E7686"
const CARD  = "#FFFFFF"
const SAND  = "#E8E3D8"
const BNAVY = "#152742"
const ACCENT = "#FF5C1A"
const LINE  = "#E2E2DC"
const SANS: CSSProperties = { fontFamily: "var(--font-sans)" }

const TILE = "rounded-[26px] p-[30px] relative overflow-hidden"

function Eyebrow({ children, dark = false, className = "" }: { children: ReactNode; dark?: boolean; className?: string }) {
  return (
    <p
      className={`text-[10.5px] font-extrabold uppercase tracking-[0.17em] ${className}`}
      style={{ ...SANS, color: dark ? "rgba(255,255,255,.6)" : MUTED }}
    >
      {children}
    </p>
  )
}

function todayLabel(): string {
  const s = new Date().toLocaleDateString("es-MX", { weekday: "long", day: "numeric", month: "long" })
  return s.charAt(0).toUpperCase() + s.slice(1)
}

function greeting(): string {
  const h = new Date().getHours()
  if (h < 12) return "Buenos días"
  if (h < 19) return "Buenas tardes"
  return "Buenas noches"
}

interface BoardSession {
  board_session_id: string
  period_year: number
  period_month: number
  period_label?: string
  status?: string
  created_at?: string
}

const STATUS_LABEL: Record<string, string> = {
  draft: "Borrador", active: "Activa", completed: "Completada",
}

export default function InicioBetaPage() {
  const [userName, setUserName] = useState("")
  const [meses, setMeses] = useState<BoardMes[]>([])
  const [sessions, setSessions] = useState<BoardSession[]>([])
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null)
  const [plan, setPlan] = useState<PlanAnual | null>(null)
  const [diagStatus, setDiagStatus] = useState<string | null>(null)
  const [downloadingActa, setDownloadingActa] = useState(false)

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      const meta = data.user?.user_metadata ?? {}
      const name = ((meta.full_name ?? meta.name ?? "") as string).trim().split(/\s+/)[0] ?? ""
      setUserName(name)
    })
    getBoard().then(setMeses).catch(() => {})
    api.get("/board-sessions").then(r => setSessions(r.data)).catch(() => {})
    getRoadmap().then(setRoadmap).catch(() => {})
    getPlanAnual().then(setPlan).catch(() => {})
    api.get("/diagnostico/status").then(r => setDiagStatus(r.data?.status ?? null)).catch(() => {})
  }, [])

  // ── Resúmenes vivos ─────────────────────────────────────
  const mesActual = meses.find(m => m.es_mes_actual) ?? meses[0]
  const tareasMes = mesActual ? [...(mesActual.arrastradas ?? []), ...mesActual.tareas] : []
  const hechasMes = tareasMes.filter(t => t.status === "completada").length

  const todasTareas = meses.flatMap(m => m.tareas)
  const hechasTotal = todasTareas.filter(t => t.status === "completada").length

  const ultimaSesion = sessions[0] ?? null
  const pilares = roadmap?.pilares?.length ?? 0

  const descargarMinuta = async () => {
    if (!ultimaSesion || downloadingActa) return
    setDownloadingActa(true)
    try { await downloadSesionActaPdf(ultimaSesion.board_session_id) }
    catch { /* si el acta aún no se puede generar, no rompemos la vista */ }
    finally { setDownloadingActa(false) }
  }

  // ── Accesos con resumen (espejo del menú) ───────────────
  const accesos = [
    {
      href: "/dashboard/diagnostico", icon: FileSearch, label: "Diagnóstico",
      resumen: diagStatus === "active" ? "Listo para consultar"
        : diagStatus === "generating" ? "Generándose…"
        : "Aún sin generar",
    },
    {
      href: "/dashboard/roadmap-beta", icon: Map, label: "Roadmap",
      resumen: pilares > 0 ? `${pilares} prioridades a 3 años` : "Aún sin roadmap",
    },
    {
      href: "/dashboard/plan-anual", icon: CalendarCheck, label: "Plan anual",
      resumen: plan?.aprobado ? `Aprobado · ${plan.pilares_aprobados.length} prioridades` : "Pendiente de aprobar",
    },
    {
      href: "/dashboard/consejo", icon: Users, label: "Board IA",
      resumen: todasTareas.length > 0 ? `${hechasTotal} de ${todasTareas.length} tareas hechas` : "Sin tareas todavía",
    },
    {
      href: "/dashboard/biblioteca", icon: Library, label: "Biblioteca",
      resumen: "Tus documentos del Consejo",
    },
  ]

  return (
    <div className="min-h-dvh font-sans antialiased" style={{ background: PAPER, color: INK }}>
      <main>
        <PageShell className="py-8 space-y-4">

          {/* Saludo */}
          <div className="px-1 pb-2">
            <Eyebrow className="mb-0">{todayLabel()} · Secretario</Eyebrow>
            <h1 className="text-[26px] font-bold tracking-[-.02em]" style={{ ...SANS, color: INK }}>
              {greeting()}{userName ? `, ${userName}` : ""}.
            </h1>
          </div>

          {/* BENTO */}
          <div className="grid grid-cols-12 gap-4">

            {/* 1. TODD — te recibe y pregunta */}
            <div className={`${TILE} col-span-12 lg:col-span-8 flex min-h-[220px] flex-col justify-between`} style={{ background: SAND }}>
              <div className="flex items-start gap-5">
                <span
                  className="grid h-14 w-14 shrink-0 place-items-center rounded-full text-[20px] font-bold text-white"
                  style={{ ...SANS, background: BNAVY }}
                  aria-hidden
                >
                  T
                </span>
                <div className="min-w-0">
                  <Eyebrow className="mb-2">Todd · tu Secretario</Eyebrow>
                  <h2 className="text-[23px] font-bold leading-tight tracking-[-.025em]" style={{ ...SANS, color: INK }}>
                    ¿En qué te puedo ayudar hoy?
                  </h2>
                  <p className="mt-2.5 text-[15px] leading-relaxed" style={{ color: INK2, maxWidth: "38em" }}>
                    Pregúntame por tus tareas, tus acuerdos o lo que sigue en tu plan.
                    También puedo reasignar responsables o mover fechas por ti.
                  </p>
                </div>
              </div>
              <div className="mt-6 flex flex-wrap items-center gap-4">
                <button
                  type="button"
                  onClick={() => window.dispatchEvent(new Event("todd:abrir"))}
                  className="inline-flex w-fit items-center gap-2.5 rounded-full px-5 py-3 text-[13px] font-bold tracking-wide text-white transition-colors hover:brightness-90"
                  style={{ ...SANS, background: ACCENT }}
                >
                  <MessageSquare className="h-4 w-4" /> Secretario Todd
                </button>
                <p className="text-[12.5px] font-semibold leading-snug" style={{ ...SANS, color: MUTED }}>
                  Todd siempre está disponible en el botón flotante naranja,
                  abajo a la derecha, desde cualquier página.
                </p>
              </div>
            </div>

            {/* 2. ÚLTIMA MINUTA */}
            <div className={`${TILE} col-span-12 lg:col-span-4 flex min-h-[220px] flex-col justify-between`} style={{ background: BNAVY, color: "#fff" }}>
              <div>
                <Eyebrow dark className="mb-2">Última minuta</Eyebrow>
                {ultimaSesion ? (
                  <>
                    <h3 className="text-[20px] font-bold leading-tight tracking-[-.02em]" style={SANS}>
                      {ultimaSesion.period_label ?? `Sesión ${ultimaSesion.period_year}`}
                    </h3>
                    <p className="mt-2 text-[13px] font-semibold" style={{ color: "rgba(255,255,255,.6)" }}>
                      {STATUS_LABEL[ultimaSesion.status ?? ""] ?? "Sesión"} · el acta guarda los acuerdos tal como quedaron.
                    </p>
                  </>
                ) : (
                  <>
                    <h3 className="text-[20px] font-bold leading-tight tracking-[-.02em]" style={SANS}>
                      Aún no hay sesiones
                    </h3>
                    <p className="mt-2 text-[13px] font-semibold" style={{ color: "rgba(255,255,255,.6)" }}>
                      Cuando sesione tu Consejo, aquí vivirá su acta.
                    </p>
                  </>
                )}
              </div>
              {ultimaSesion ? (
                <div className="flex flex-wrap items-center gap-2.5">
                  <button
                    type="button"
                    onClick={descargarMinuta}
                    disabled={downloadingActa}
                    className="inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-[12px] font-bold transition-all hover:brightness-95 disabled:opacity-60"
                    style={{ ...SANS, background: "#fff", color: BNAVY }}
                  >
                    {downloadingActa ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileText className="h-3.5 w-3.5" />}
                    Descargar acta
                  </button>
                  <Link
                    href={`/dashboard/sesion/${ultimaSesion.board_session_id}`}
                    className="inline-flex items-center gap-1.5 text-[12px] font-bold transition-colors hover:text-white"
                    style={{ ...SANS, color: "rgba(255,255,255,.65)" }}
                  >
                    Abrir sesión <ArrowUpRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              ) : (
                <Link
                  href="/dashboard/consejo"
                  className="inline-flex w-fit items-center gap-2 rounded-full px-4 py-2.5 text-[12px] font-bold transition-all hover:brightness-95"
                  style={{ ...SANS, background: "#fff", color: BNAVY }}
                >
                  Ir al Board IA <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              )}
            </div>

            {/* 3. ACCIONES DE ESTE MES */}
            <div className={`${TILE} col-span-12`} style={{ background: CARD, border: `1px solid ${LINE}` }}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <Eyebrow className="mb-2">
                    Acciones de este mes{mesActual ? ` · ${mesActual.label}` : ""}
                  </Eyebrow>
                  <h3 className="text-[20px] font-bold leading-tight tracking-[-.02em]" style={{ ...SANS, color: INK }}>
                    {tareasMes.length > 0
                      ? `${hechasMes} de ${tareasMes.length} hechas`
                      : "Sin tareas asignadas a este mes"}
                  </h3>
                </div>
                <Link
                  href="/dashboard/consejo"
                  className="shrink-0 inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-[12px] font-bold tracking-wide text-white transition-colors hover:brightness-90"
                  style={{ ...SANS, background: BNAVY }}
                >
                  Ir al Board IA <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>

              {tareasMes.length > 0 && (
                <ul className="mt-5 grid grid-cols-1 gap-x-8 gap-y-1 border-t pt-4 md:grid-cols-2" style={{ borderColor: LINE }}>
                  {tareasMes.slice(0, 8).map(t => {
                    const Icon = t.status === "completada" ? CheckCircle2 : t.status === "en_progreso" ? CircleDot : Circle
                    const iconColor = t.status === "completada" ? "#0f766e" : t.status === "en_progreso" ? "#b45309" : MUTED
                    return (
                      <li key={t.id} className="flex items-start gap-2.5 py-1.5 text-[14.5px] leading-snug" style={{ color: INK }}>
                        <Icon className="mt-[3px] h-[15px] w-[15px] shrink-0" style={{ color: iconColor }} />
                        <span className={t.status === "completada" ? "line-through opacity-60" : ""}>
                          {t.title}
                          {t.owner && <span className="ml-2 text-[12px] font-semibold" style={{ color: MUTED }}>· {t.owner}</span>}
                          {t.viene_de && <span className="ml-2 text-[11px] font-bold uppercase tracking-wide" style={{ color: ACCENT }}>arrastrada</span>}
                        </span>
                      </li>
                    )
                  })}
                </ul>
              )}
              {tareasMes.length > 8 && (
                <p className="mt-2 text-[12px] font-semibold" style={{ color: MUTED }}>
                  +{tareasMes.length - 8} tareas más en el Board IA
                </p>
              )}
            </div>

            {/* 4. ACCESOS CON RESUMEN — espejo del menú */}
            <div className="col-span-12 px-1 pt-2">
              <Eyebrow>Tu Consejo, sección por sección</Eyebrow>
            </div>
            <div className="col-span-12 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
              {accesos.map(a => {
                const Icon = a.icon
                return (
                  <Link
                    key={a.href}
                    href={a.href}
                    className="group flex min-h-[150px] flex-col justify-between rounded-[26px] p-[26px] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
                    style={{ background: CARD, border: `1px solid ${LINE}` }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="grid h-10 w-10 place-items-center rounded-[12px]" style={{ background: PAPER, color: BNAVY }}>
                        <Icon className="h-[18px] w-[18px]" strokeWidth={1.9} />
                      </span>
                      <span
                        className="grid h-7 w-7 shrink-0 place-items-center rounded-full border text-[12px] transition-colors group-hover:border-transparent group-hover:bg-[#FF5C1A] group-hover:text-white"
                        style={{ borderColor: "rgba(14,22,38,0.18)", color: MUTED }}
                      >
                        →
                      </span>
                    </div>
                    <div>
                      <p className="text-[16px] font-bold tracking-[-.015em]" style={{ ...SANS, color: INK }}>{a.label}</p>
                      <p className="mt-1 text-[12.5px] font-semibold leading-snug" style={{ ...SANS, color: INK2 }}>{a.resumen}</p>
                    </div>
                  </Link>
                )
              })}
            </div>

          </div>
        </PageShell>
      </main>

    </div>
  )
}
