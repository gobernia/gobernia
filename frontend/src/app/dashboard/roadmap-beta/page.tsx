"use client"

import { useEffect, useRef, useState, type CSSProperties } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { Loader2, ArrowRight, Map as MapIcon, CalendarCheck, Pencil, BadgeCheck, RotateCcw, Check } from "lucide-react"
import { PageShell, PageHeader } from "@/components/ui/PageShell"
import {
  getRoadmap, saveRoadmap, getRoadmapEstado, validarRoadmap, reabrirRoadmap,
  type Roadmap, type Pilar, type RoadmapEstado,
} from "@/lib/roadmap"
import { aniosDelPlan, pilarColor, roadmapIsEmpty, splitLines, joinLines, padSlots, emptyKpi } from "@/components/roadmap/shared"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

// Paleta bento — mismos tokens del Inicio.
const PAPER = "#F2F2F0"
const INK   = "#0E1626"
const INK2  = "#39435A"
const MUTED = "#6E7686"
const CARD  = "#FFFFFF"
const SAND  = "#E8E3D8"
const BNAVY = "#152742"
const ACCENT = "#C2410C"
const LINE  = "#E2E2DC"
const SANS: CSSProperties = { fontFamily: "var(--font-sans)" }

type AnioKey = "anio1" | "anio2" | "anio3"

export default function RoadmapBetaPage() {
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null)
  const [loaded, setLoaded] = useState(false)
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    getRoadmap()
      .then(r => { if (aliveRef.current) setRoadmap(r) })
      .catch(() => { if (aliveRef.current) setRoadmap(null) })
      .finally(() => { if (aliveRef.current) setLoaded(true) })
    return () => { aliveRef.current = false }
  }, [])

  const hasRoadmap = !!roadmap && !roadmapIsEmpty(roadmap)

  return (
    <div className="min-h-dvh text-black antialiased" style={{ background: PAPER }}>
      <PageHeader
        eyebrow="Cómo te ves a 3 años"
        title="Estrategia"
        actions={
          hasRoadmap ? (
            <Link
              href="/dashboard/plan-anual"
              className="inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-xs font-medium text-white transition-colors"
              style={{ background: ACCENT }}
            >
              <CalendarCheck className="h-3.5 w-3.5" /> Ir a mi Plan anual
            </Link>
          ) : undefined
        }
      />

      <main>
        <PageShell className="py-10 space-y-8">

          {/* Cargando */}
          {!loaded && (
            <div className="flex items-center justify-center rounded-[26px] p-16" style={{ background: CARD, border: `1px solid ${LINE}` }}>
              <Loader2 className="h-6 w-6 animate-spin" style={{ color: MUTED }} />
            </div>
          )}

          {/* Vacío */}
          {loaded && !hasRoadmap && (
            <div className="flex flex-col items-center gap-4 rounded-[26px] p-12 text-center sm:p-16" style={{ background: CARD, border: `1px solid ${LINE}` }}>
              <div className="flex h-14 w-14 items-center justify-center rounded-[26px] border-2" style={{ borderColor: LINE, color: MUTED }}>
                <MapIcon className="h-5 w-5" />
              </div>
              <div className="max-w-md space-y-1.5">
                <p className="text-base font-medium" style={{ ...SANS, color: INK }}>Todavía no hay una dirección a 3 años</p>
                <p className="text-sm leading-relaxed" style={{ color: INK2 }}>
                  Cuando generes tu plan, aquí verás — muy sencillo, año por año — a dónde apunta la
                  empresa en los próximos tres años. El detalle y las tareas viven en tu Plan anual.
                </p>
              </div>
              <Link
                href="/dashboard/plan"
                className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium text-white transition-colors"
                style={{ background: ACCENT }}
              >
                Generar mi plan <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          )}

          {/* La línea de tiempo, año por año */}
          {loaded && hasRoadmap && <RoadmapTresAnios roadmap={roadmap!} />}

          {/* Los pilares de la estrategia: seleccionables y editables */}
          {loaded && hasRoadmap && <PilaresEstrategia roadmap={roadmap!} onChange={setRoadmap} />}

        </PageShell>
      </main>
    </div>
  )
}

// ── Los pilares de la estrategia ────────────────────────────────────────────
// Como en el Inicio: los 5 pilares en una fila (título + explicación, en
// grande); el seleccionado se pinta de azul, saca su pestañita y abre abajo
// SU ficha con estrategias e indicadores. Aquí además TODO es editable
// (mientras la estrategia esté en borrador) — este es el paso donde se valida
// la estrategia antes de generar el Plan anual.
function PilaresEstrategia({ roadmap, onChange }: { roadmap: Roadmap; onChange: (r: Roadmap) => void }) {
  const pilares = roadmap.pilares ?? []
  const [sel, setSel] = useState(0)
  const [estado, setEstado] = useState<RoadmapEstado | null>(null)
  const [editando, setEditando] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState<Pilar | null>(null)
  const [draftEstrategias, setDraftEstrategias] = useState("")

  useEffect(() => {
    getRoadmapEstado().then(setEstado).catch(() => {})
  }, [])

  if (pilares.length === 0) return null

  const activo = Math.min(sel, pilares.length - 1)
  const pilar = pilares[activo]
  const editable = estado?.status !== "validado"
  const num = String(activo + 1).padStart(2, "0")

  const seleccionar = (i: number) => {
    setSel(i)
    setEditando(false)
    setError(null)
  }

  const empezarEdicion = () => {
    setDraft({ ...pilar, kpis: padSlots(pilar.kpis, 3, emptyKpi) })
    setDraftEstrategias(joinLines(pilar.estrategias))
    setEditando(true)
    setError(null)
  }

  const guardar = async () => {
    if (!draft) return
    setSaving(true)
    setError(null)
    try {
      const nuevo: Pilar = {
        ...draft,
        nombre: draft.nombre.trim(),
        estrategias: splitLines(draftEstrategias),
        kpis: (draft.kpis ?? []).filter(k => k.label.trim()),
      }
      const r = await saveRoadmap({ ...roadmap, pilares: pilares.map((p, i) => (i === activo ? nuevo : p)) })
      onChange(r)
      setEditando(false)
    } catch {
      setError("No se pudo guardar. Intenta de nuevo.")
    } finally {
      setSaving(false)
    }
  }

  const validar = async () => {
    setSaving(true)
    setError(null)
    try {
      setEstado(await validarRoadmap())
      setEditando(false)
    } catch {
      setError("No se pudo validar la estrategia. Intenta de nuevo.")
    } finally {
      setSaving(false)
    }
  }

  const reabrir = async () => {
    setSaving(true)
    setError(null)
    try {
      setEstado(await reabrirRoadmap())
    } catch {
      setError("No se pudo reabrir la estrategia. Intenta de nuevo.")
    } finally {
      setSaving(false)
    }
  }

  const inputCls = "w-full rounded-[12px] px-3 py-2 text-[14px] focus-visible:outline-none focus-visible:ring-2"
  const inputStyle: CSSProperties = {
    background: "rgba(255,255,255,.08)", border: "1px solid rgba(255,255,255,.22)",
    color: "#fff",
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: EASE, delay: 0.1 }}
      className="space-y-4 pt-4"
    >
      <div className="px-1">
        <p className="text-[10.5px] font-extrabold uppercase tracking-[0.17em]" style={{ ...SANS, color: MUTED }}>
          Los pilares de tu estrategia
        </p>
        <p className="mt-1 text-sm leading-relaxed" style={{ color: INK2, maxWidth: "48em" }}>
          Toca un pilar para abrir su detalle. Revisa y <span className="font-semibold" style={{ color: INK }}>edita lo que haga falta</span> —
          cuando todo esté como quieres, valida tu estrategia para pasar al Plan anual.
        </p>
      </div>

      {/* Fila de pilares: título + explicación, en grande. El activo se pinta
          de azul y conecta con la ficha de abajo. */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {pilares.map((p, i) => {
          const esActivo = i === activo
          return (
            <button
              key={i}
              type="button"
              onClick={() => seleccionar(i)}
              aria-current={esActivo ? "true" : undefined}
              className="group relative flex min-h-[180px] cursor-pointer flex-col rounded-[26px] p-[26px] text-left transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
              style={esActivo ? { background: BNAVY, color: "#fff" } : { background: i % 2 === 0 ? SAND : CARD, border: esActivo ? "none" : `1px solid ${LINE}` }}
            >
              <div className="text-[13px] font-extrabold tracking-[0.04em]" style={{ color: ACCENT }}>
                {String(i + 1).padStart(2, "0")}
              </div>
              <div className="mt-2.5 text-[17px] font-bold leading-tight tracking-[-.02em]" style={{ ...SANS, color: esActivo ? "#fff" : INK }}>
                {p.nombre || `Pilar ${i + 1}`}
              </div>
              <p className="mt-2 text-[13px] leading-snug line-clamp-3" style={{ color: esActivo ? "rgba(255,255,255,.75)" : INK2 }}>
                {p.descripcion || p.objetivo || ""}
              </p>
              {esActivo && (
                <span
                  aria-hidden
                  className="absolute left-1/2 -bottom-[8px] h-[18px] w-[18px] -translate-x-1/2 rotate-45 rounded-[4px]"
                  style={{ background: BNAVY }}
                />
              )}
            </button>
          )
        })}
      </div>

      {/* Ficha del pilar seleccionado (azul, ancho completo) */}
      <div key={activo} className="rounded-[26px] p-[30px]" style={{ background: BNAVY, color: "#fff" }}>
        {!editando ? (
          <>
            <div className="flex items-start gap-[18px]">
              <div className="shrink-0 font-bold leading-[.85] tracking-[-.04em]" style={{ ...SANS, fontSize: "46px", opacity: 0.22 }}>
                {num}
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-[23px] font-bold leading-tight tracking-[-.025em]" style={SANS}>
                  {pilar.nombre || `Pilar ${activo + 1}`}
                </h3>
                {pilar.descripcion && (
                  <p className="mt-3 text-[15.5px] leading-relaxed" style={{ color: "rgba(255,255,255,.86)" }}>{pilar.descripcion}</p>
                )}
                {pilar.objetivo && (
                  <p className="mt-2 text-[14px] leading-relaxed" style={{ color: "rgba(255,255,255,.65)" }}>
                    <span className="font-bold" style={{ color: "rgba(255,255,255,.85)" }}>Objetivo: </span>{pilar.objetivo}
                  </p>
                )}
              </div>
              {editable && (
                <button
                  type="button"
                  onClick={empezarEdicion}
                  className="shrink-0 inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-[12px] font-bold transition-all hover:brightness-95"
                  style={{ ...SANS, background: "#fff", color: BNAVY }}
                >
                  <Pencil className="h-3.5 w-3.5" /> Editar pilar
                </button>
              )}
            </div>

            <div className="mt-6 grid grid-cols-1 gap-5 border-t pt-5 sm:grid-cols-2" style={{ borderColor: "rgba(255,255,255,.16)" }}>
              <div>
                <div className="mb-3 text-[10px] font-extrabold uppercase tracking-[0.16em]" style={{ color: "rgba(255,255,255,.55)" }}>
                  Indicadores
                </div>
                {(pilar.kpis ?? []).filter(k => k.label).length > 0 ? (
                  <ul className="space-y-2">
                    {(pilar.kpis ?? []).filter(k => k.label).map((k, j) => (
                      <li key={j} className="relative py-1 pl-[18px] text-[14.5px] leading-snug">
                        <span className="absolute left-0 top-[11px] h-[7px] w-[7px] rounded-[2px]" style={{ background: ACCENT }} />
                        {k.label}
                        {(k.actual || k.meta) && (
                          <span className="ml-1.5 text-[12px] font-semibold" style={{ color: "rgba(255,255,255,.6)" }}>
                            · {k.actual || "—"} → {k.meta || "por definir"}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[13px]" style={{ color: "rgba(255,255,255,.5)" }}>—</p>
                )}
              </div>
              <div>
                <div className="mb-3 text-[10px] font-extrabold uppercase tracking-[0.16em]" style={{ color: "rgba(255,255,255,.55)" }}>
                  Estrategias
                </div>
                {(pilar.estrategias ?? []).length > 0 ? (
                  <ol className="space-y-2">
                    {(pilar.estrategias ?? []).map((e, j) => (
                      <li key={j} className="flex gap-2.5 text-[14.5px] leading-snug">
                        <span className="shrink-0 font-bold tabular-nums" style={{ color: "rgba(255,255,255,.45)" }}>{j + 1}.</span>
                        {e}
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="text-[13px]" style={{ color: "rgba(255,255,255,.5)" }}>—</p>
                )}
              </div>
            </div>

            {/* Los asuntos que el Consejo revisará en el año por este pilar */}
            {(pilar.temas_consejo ?? []).length > 0 && (
              <div className="mt-5 border-t pt-4" style={{ borderColor: "rgba(255,255,255,.16)" }}>
                <div className="mb-2.5 text-[10px] font-extrabold uppercase tracking-[0.16em]" style={{ color: "rgba(255,255,255,.55)" }}>
                  Temas para el Consejo
                </div>
                <div className="flex flex-wrap gap-2">
                  {(pilar.temas_consejo ?? []).map((t, j) => (
                    <span key={j} className="rounded-full px-3 py-1.5 text-[12.5px] font-medium leading-snug"
                      style={{ background: "rgba(255,255,255,.1)", border: "1px solid rgba(255,255,255,.2)" }}>
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          /* ── Modo edición: todo el pilar es editable ── */
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <div className="font-bold leading-[.85] tracking-[-.04em]" style={{ ...SANS, fontSize: "34px", opacity: 0.22 }}>{num}</div>
              <h3 className="text-[18px] font-bold tracking-[-.02em]" style={SANS}>Editando pilar</h3>
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="space-y-4">
                <label className="block">
                  <span className="mb-1.5 block text-[10px] font-extrabold uppercase tracking-[0.16em]" style={{ color: "rgba(255,255,255,.55)" }}>Título del pilar</span>
                  <input className={inputCls} style={inputStyle} value={draft?.nombre ?? ""} onChange={e => setDraft(d => d ? { ...d, nombre: e.target.value } : d)} />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[10px] font-extrabold uppercase tracking-[0.16em]" style={{ color: "rgba(255,255,255,.55)" }}>Explicación</span>
                  <textarea rows={3} className={inputCls} style={inputStyle} value={draft?.descripcion ?? ""} onChange={e => setDraft(d => d ? { ...d, descripcion: e.target.value } : d)} />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[10px] font-extrabold uppercase tracking-[0.16em]" style={{ color: "rgba(255,255,255,.55)" }}>Objetivo</span>
                  <textarea rows={2} className={inputCls} style={inputStyle} value={draft?.objetivo ?? ""} onChange={e => setDraft(d => d ? { ...d, objetivo: e.target.value } : d)} />
                </label>
              </div>
              <div className="space-y-4">
                <label className="block">
                  <span className="mb-1.5 block text-[10px] font-extrabold uppercase tracking-[0.16em]" style={{ color: "rgba(255,255,255,.55)" }}>Estrategias — una por línea</span>
                  <textarea rows={5} className={inputCls} style={inputStyle} value={draftEstrategias} onChange={e => setDraftEstrategias(e.target.value)} />
                </label>
                <div>
                  <span className="mb-1.5 block text-[10px] font-extrabold uppercase tracking-[0.16em]" style={{ color: "rgba(255,255,255,.55)" }}>Indicadores (nombre · hoy · meta)</span>
                  <div className="space-y-2">
                    {(draft?.kpis ?? []).map((k, j) => (
                      <div key={j} className="grid grid-cols-[1fr_90px_90px] gap-2">
                        <input className={inputCls} style={inputStyle} placeholder="Indicador" value={k.label}
                          onChange={e => setDraft(d => d ? { ...d, kpis: (d.kpis ?? []).map((x, xi) => xi === j ? { ...x, label: e.target.value } : x) } : d)} />
                        <input className={inputCls} style={inputStyle} placeholder="Hoy" value={k.actual}
                          onChange={e => setDraft(d => d ? { ...d, kpis: (d.kpis ?? []).map((x, xi) => xi === j ? { ...x, actual: e.target.value } : x) } : d)} />
                        <input className={inputCls} style={inputStyle} placeholder="Meta" value={k.meta}
                          onChange={e => setDraft(d => d ? { ...d, kpis: (d.kpis ?? []).map((x, xi) => xi === j ? { ...x, meta: e.target.value } : x) } : d)} />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-4 border-t pt-4" style={{ borderColor: "rgba(255,255,255,.16)" }}>
              <button
                type="button"
                onClick={guardar}
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-[13px] font-bold text-white transition-colors hover:brightness-90 disabled:opacity-50"
                style={{ ...SANS, background: ACCENT }}
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Guardar cambios
              </button>
              <button
                type="button"
                onClick={() => setEditando(false)}
                disabled={saving}
                className="text-[13px] font-semibold transition-colors hover:text-white"
                style={{ ...SANS, color: "rgba(255,255,255,.6)" }}
              >
                Cancelar
              </button>
            </div>
          </div>
        )}
      </div>

      {error && <p className="px-1 text-sm" style={{ color: "#dc2626" }}>{error}</p>}

      {/* Validación de la estrategia */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-[26px] px-[30px] py-5" style={{ background: SAND }}>
        {estado?.status === "validado" ? (
          <>
            <div className="flex items-center gap-3">
              <BadgeCheck className="h-5 w-5 shrink-0" style={{ color: "#0f766e" }} />
              <p className="text-[14.5px] font-semibold" style={{ ...SANS, color: INK }}>
                Estrategia validada{estado.validated_at ? ` el ${new Date(estado.validated_at).toLocaleDateString("es-MX", { day: "numeric", month: "long", year: "numeric" })}` : ""}.
                <span className="ml-1 font-normal" style={{ color: INK2 }}>Para editarla, reábrela.</span>
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={reabrir}
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-[12px] font-bold transition-colors disabled:opacity-50"
                style={{ ...SANS, border: `1px solid ${INK}`, color: INK }}
              >
                <RotateCcw className="h-3.5 w-3.5" /> Reabrir para editar
              </button>
              <Link
                href="/dashboard/plan-anual"
                className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-[13px] font-bold text-white transition-colors hover:brightness-90"
                style={{ ...SANS, background: ACCENT }}
              >
                Ir a mi Plan anual <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </>
        ) : (
          <>
            <p className="text-[14.5px] leading-relaxed" style={{ color: INK2, maxWidth: "40em" }}>
              <span className="font-bold" style={{ color: INK }}>Tu estrategia está en borrador.</span>{" "}
              Revisa y edita tus pilares; cuando todo esté como quieres, valídala para continuar con tu Plan anual.
            </p>
            <button
              type="button"
              onClick={validar}
              disabled={saving || editando}
              className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-[13px] font-bold text-white transition-colors hover:brightness-90 disabled:opacity-50"
              style={{ ...SANS, background: ACCENT }}
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <BadgeCheck className="h-4 w-4" />} Validar estrategia
            </button>
          </>
        )}
      </div>
    </motion.section>
  )
}

// El roadmap: sencillo, año por año. Qué debe conseguir la empresa cada año durante
// los próximos tres. El detalle por prioridad y las tareas NO van aquí — van en el Plan.
function RoadmapTresAnios({ roadmap }: { roadmap: Roadmap }) {
  const [a1, a2, a3] = aniosDelPlan(roadmap.anio_objetivo)
  const temas = roadmap.temas_por_anio ?? {}
  const pilares = roadmap.pilares ?? []

  const anios: { n: number; key: AnioKey; lema?: string; activo: boolean }[] = [
    { n: a1, key: "anio1", lema: temas.anio1, activo: true },
    { n: a2, key: "anio2", lema: temas.anio2, activo: false },
    { n: a3, key: "anio3", lema: temas.anio3, activo: false },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: EASE }}
      className="space-y-6"
    >
      {/* La pregunta que responde el roadmap + la regla de que solo el año 1 se ejecuta */}
      <div className="max-w-3xl space-y-2">
        <p className="text-lg font-semibold leading-snug tracking-tight" style={{ ...SANS, color: INK }}>
          ¿Qué debe conseguir la empresa en los próximos tres años para fortalecerse, crecer y
          asegurar su continuidad?
        </p>
        <p className="text-sm leading-relaxed" style={{ color: INK2 }}>
          Solo el <span className="font-semibold" style={{ color: INK }}>año en curso se ejecuta</span> — su detalle
          y sus tareas están en tu{" "}
          <Link href="/dashboard/plan-anual" className="font-medium underline" style={{ color: BNAVY }}>Plan anual</Link>.
          Los <span style={{ color: ACCENT }}>años 2 y 3 son orientativos</span> y se ajustan al cerrar cada año.
        </p>
      </div>

      {/* Tres columnas: un año cada una */}
      <div className="grid gap-5 lg:grid-cols-3">
        {anios.map((y, i) => (
          <ColumnaAnio key={y.n} anio={y} orden={i + 1} pilares={pilares} />
        ))}
      </div>
    </motion.div>
  )
}

function ColumnaAnio({
  anio, orden, pilares,
}: {
  anio: { n: number; key: AnioKey; lema?: string; activo: boolean }
  orden: number
  pilares: Pilar[]
}) {
  // Qué avanza cada pilar ESE año: su fase (el titular del año) y sus milestones.
  const filas = pilares
    .map((p, pi) => ({
      nombre: p.nombre,
      color: pilarColor(pi),
      fase: p.fases?.[anio.key]?.titulo?.trim() || "",
      hitos: (p.milestones?.[anio.key] ?? []).map(s => s.trim()).filter(Boolean),
    }))
    .filter(f => f.nombre && (f.fase || f.hitos.length > 0))

  const activo = anio.activo

  return (
    <section
      className="flex flex-col overflow-hidden rounded-[26px] border"
      style={activo ? { borderColor: BNAVY } : { borderColor: LINE }}
    >
      {/* Cabecera del año */}
      <div className="p-5" style={activo ? { background: BNAVY, color: "#fff" } : { background: SAND }}>
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.16em]" style={{ ...SANS, color: activo ? "rgba(255,255,255,0.55)" : MUTED }}>
              Año {orden}
            </p>
            <p className="text-xl font-bold tabular-nums" style={{ ...SANS, color: activo ? "#fff" : INK }}>{anio.n}</p>
          </div>
          <span
            className="rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em]"
            style={activo ? { background: "rgba(255,255,255,0.16)", color: "#fff" } : { background: CARD, color: ACCENT, border: `1px solid ${LINE}` }}
          >
            {activo ? "En ejecución" : "Orientativo"}
          </span>
        </div>
        {anio.lema && (
          <p className="mt-2 text-sm font-medium leading-snug" style={{ ...SANS, color: activo ? "rgba(255,255,255,0.92)" : INK }}>
            «{anio.lema}»
          </p>
        )}
      </div>

      {/* Qué se trabaja ese año, prioridad por prioridad */}
      <div className="flex-1 space-y-4 p-5" style={{ background: CARD }}>
        {filas.length > 0 ? (
          filas.map((f, j) => (
            <div key={j} className="border-l-2 pl-3" style={{ borderColor: f.color }}>
              <p className="text-sm font-bold leading-tight" style={{ ...SANS, color: INK }}>{f.nombre}</p>
              {f.fase && <p className="mt-0.5 text-xs font-medium" style={{ color: INK2 }}>{f.fase}</p>}
              {f.hitos.length > 0 && (
                <ul className="mt-1.5 space-y-1">
                  {f.hitos.map((h, k) => (
                    <li key={k} className="flex gap-1.5 text-xs leading-relaxed" style={{ color: INK2 }}>
                      <span className="mt-1 h-1 w-1 shrink-0 rounded-full" style={{ background: f.color }} />
                      <span>{h}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))
        ) : (
          <p className="text-xs italic" style={{ color: MUTED }}>Sin actividades definidas para este año todavía.</p>
        )}
      </div>

      {/* El año en curso conecta con el Plan anual */}
      {activo && (
        <div className="border-t p-4" style={{ borderColor: LINE }}>
          <Link
            href="/dashboard/plan-anual"
            className="inline-flex w-full items-center justify-center gap-2 rounded-full px-4 py-2.5 text-xs font-medium text-white transition-colors"
            style={{ background: ACCENT }}
          >
            <CalendarCheck className="h-3.5 w-3.5" /> Trabajar este año en mi Plan anual
          </Link>
        </div>
      )}
    </section>
  )
}
