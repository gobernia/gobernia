"use client"

import { useEffect, useRef, useState, type ReactNode } from "react"
import Link from "next/link"
import { ClipboardList, ArrowRight, Gavel, Target, ListChecks, Gauge, FileText, Scale, CheckCircle2, AlertTriangle, Handshake } from "lucide-react"
import {
  getPlanAnual,
  getOrdenCadena,
  type PlanAnual,
  type PilarAnual,
  type DocSolicitado,
  type AnalisisPunto,
  type AcuerdoPunto,
} from "@/lib/planAnual"

/**
 * La orden del día, armada DESDE el Plan anual — la cadena que pide el cliente:
 * cada punto = una prioridad aprobada, con su indicador, su meta, sus tareas y
 * qué decide el Consejo. Es lo que el Consejo revisará al sesionar el mes.
 *
 * Paso 1: se compone en vivo de las prioridades aprobadas (sin tocar la base de
 * datos). El análisis por punto, los documentos por punto y el acta de 5 apartados
 * son fases siguientes.
 */

// Colores por hex — Tailwind v4 no ve clases dinámicas.
const NAVY = "#142849"
const TEAL = "#0f766e"
const AMBER = "#b45309"

// Acentos por prioridad, on-brand (mismos que el roadmap).
const PILAR_COLORS = ["#1e3a5f", "#0f766e", "#b45309", "#6d28d9", "#b91c1c", "#334155"]
const colorDe = (i: number) => PILAR_COLORS[i % PILAR_COLORS.length]

export default function OrdenDelDiaCadena() {
  const [plan, setPlan] = useState<PlanAnual | null>(null)
  const [loaded, setLoaded] = useState(false)
  // Documentos solicitados por prioridad (indice → docs). Fetch adicional y tolerante
  // a fallo: si no llega, simplemente no mostramos documentos.
  const [docsPorIndice, setDocsPorIndice] = useState<Record<number, DocSolicitado[]>>({})
  // Análisis por prioridad (indice → analisis). Mismo fetch/empate por indice que los docs.
  const [analisisPorIndice, setAnalisisPorIndice] = useState<Record<number, AnalisisPunto>>({})
  // Acuerdos del Consejo por prioridad (indice → acuerdos). Mismo empate por indice.
  const [acuerdosPorIndice, setAcuerdosPorIndice] = useState<Record<number, AcuerdoPunto[]>>({})
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    getPlanAnual()
      .then(p => { if (aliveRef.current) setPlan(p) })
      .catch(() => { if (aliveRef.current) setPlan(null) })
      .finally(() => { if (aliveRef.current) setLoaded(true) })
    getOrdenCadena()
      .then(c => {
        if (!aliveRef.current) return
        const docs: Record<number, DocSolicitado[]> = {}
        const analisis: Record<number, AnalisisPunto> = {}
        const acuerdos: Record<number, AcuerdoPunto[]> = {}
        for (const p of c.puntos) {
          docs[p.indice] = p.documentos_solicitados
          analisis[p.indice] = p.analisis
          acuerdos[p.indice] = p.acuerdos ?? []
        }
        setDocsPorIndice(docs)
        setAnalisisPorIndice(analisis)
        setAcuerdosPorIndice(acuerdos)
      })
      .catch(() => { /* tolerante: sin documentos, análisis ni acuerdos */ })
    return () => { aliveRef.current = false }
  }, [])

  if (!loaded) return null

  const aprobados = plan?.pilares_aprobados ?? []
  const listo = !!plan?.aprobado && aprobados.length > 0

  return (
    <section className="space-y-5">
      <div>
        <p className="mb-1 text-xs font-medium uppercase tracking-widest text-gray-400">Antes de sesionar</p>
        <h2 className="text-2xl font-bold tracking-tight text-black">Orden del día</h2>
        <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-gray-500">
          Lo que el Consejo revisará este mes. Cada punto sale de tu Plan anual y va conectado:
          la <span className="font-medium text-gray-700">prioridad</span>, su{" "}
          <span className="font-medium text-gray-700">indicador</span>, su{" "}
          <span className="font-medium text-gray-700">meta</span>, las{" "}
          <span className="font-medium text-gray-700">tareas</span> y{" "}
          <span className="font-medium text-gray-700">qué decide el Consejo</span>.
        </p>
      </div>

      {!listo ? (
        <div className="flex flex-col items-start gap-3 rounded-2xl border border-gray-100 p-6">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl" style={{ background: "#f4f7fb", color: NAVY }}>
            <ClipboardList className="h-5 w-5" />
          </span>
          <div className="space-y-1">
            <p className="text-sm font-medium text-black">Aún no hay orden del día</p>
            <p className="max-w-md text-sm leading-relaxed text-gray-500">
              La orden del día se arma con las prioridades de tu Plan anual. Aprueba entre 3 y 5
              prioridades y aquí aparecerá lo que el Consejo revisará cada mes.
            </p>
          </div>
          <Link
            href="/dashboard/plan-anual"
            className="inline-flex items-center gap-2 rounded-xl bg-[var(--gob-navy)] px-4 py-2.5 text-sm font-medium text-[var(--gob-bone)] transition-colors hover:bg-[var(--gob-ink)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]"
          >
            Aprobar mi Plan anual <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      ) : (
        <ol className="space-y-4">
          {aprobados.map((p, i) => (
            <PuntoOrden
              key={p.indice}
              pilar={p}
              orden={i + 1}
              color={colorDe(i)}
              documentos={docsPorIndice[p.indice] ?? []}
              analisis={analisisPorIndice[p.indice]}
              acuerdos={acuerdosPorIndice[p.indice] ?? []}
            />
          ))}
        </ol>
      )}
    </section>
  )
}

function PuntoOrden({
  pilar,
  orden,
  color,
  documentos,
  analisis,
  acuerdos,
}: {
  pilar: PilarAnual
  orden: number
  color: string
  documentos: DocSolicitado[]
  analisis?: AnalisisPunto
  acuerdos: AcuerdoPunto[]
}) {
  const kpis = (pilar.kpis ?? []).filter(k => k.label)
  const tareas = (pilar.estrategias ?? []).filter(Boolean)
  const meta = pilar.objetivo?.trim() || ""
  const docs = (documentos ?? []).filter(d => d.doc?.trim())

  return (
    <li className="overflow-hidden rounded-2xl border border-gray-100">
      {/* Cabecera del punto: número + prioridad */}
      <div className="flex items-center gap-3 border-l-4 p-4" style={{ borderColor: color, background: "#fafafa" }}>
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white" style={{ background: color }}>
          {orden}
        </span>
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-gray-400">Punto {orden} · Prioridad</p>
          <p className="text-sm font-bold leading-tight text-black">{pilar.nombre || `Prioridad ${orden}`}</p>
        </div>
      </div>

      {/* La cadena: indicador · meta · tareas */}
      <div className="grid gap-px bg-gray-100 md:grid-cols-3">
        {/* Indicador */}
        <div className="bg-white p-4">
          <p className="mb-2 inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400">
            <Gauge className="h-3.5 w-3.5" /> Indicador
          </p>
          {kpis.length > 0 ? (
            <ul className="space-y-1.5">
              {kpis.map((k, j) => (
                <li key={j} className="text-xs leading-snug text-gray-700">
                  {k.label}
                  <span className="mt-0.5 block text-gray-500">
                    {k.actual || "—"}
                    <span className="mx-1 text-gray-300">→</span>
                    <span className="font-semibold" style={{ color: TEAL }}>{k.meta || "por definir"}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs italic text-gray-400">Sin indicador definido.</p>
          )}
        </div>

        {/* Meta */}
        <div className="bg-white p-4">
          <p className="mb-2 inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400">
            <Target className="h-3.5 w-3.5" /> Meta
          </p>
          {meta ? (
            <p className="text-xs leading-relaxed text-gray-700">{meta}</p>
          ) : (
            <p className="text-xs italic text-gray-400">La meta la fija el dueño.</p>
          )}
        </div>

        {/* Tareas */}
        <div className="bg-white p-4">
          <p className="mb-2 inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400">
            <ListChecks className="h-3.5 w-3.5" /> Tareas
          </p>
          {tareas.length > 0 ? (
            <ol className="space-y-1">
              {tareas.map((t, j) => (
                <li key={j} className="flex gap-1.5 text-xs leading-relaxed text-gray-600">
                  <span className="shrink-0 font-bold tabular-nums" style={{ color }}>{j + 1}.</span>
                  <span>{t}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-xs italic text-gray-400">Sin tareas aún.</p>
          )}
        </div>
      </div>

      {/* Documentos solicitados por el punto */}
      <div className="border-t border-gray-100 p-4">
        <p className="mb-2 inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400">
          <FileText className="h-3.5 w-3.5" /> Documentos solicitados
        </p>
        {docs.length > 0 ? (
          <ul className="flex flex-wrap gap-1.5">
            {docs.map((d, j) => (
              <li
                key={j}
                className="inline-flex items-center gap-1.5 rounded-lg border border-gray-100 bg-white px-2.5 py-1.5 text-xs leading-snug text-gray-700"
              >
                <FileText className="h-3.5 w-3.5 shrink-0" style={{ color: NAVY }} />
                <span>{d.doc}</span>
                {d.n_tareas > 1 && (
                  <span className="ml-0.5 rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] font-semibold tabular-nums text-gray-500">
                    {d.n_tareas}
                  </span>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs italic text-gray-400">
            Todd te dirá qué subir cuando haya tareas con evidencia.
          </p>
        )}
      </div>

      {/* Análisis del punto — formato fijo (determinista, sin IA) */}
      <AnalisisDelPunto analisis={analisis} />

      {/* Acuerdos del Consejo ligados a este punto */}
      <AcuerdosDelPunto acuerdos={acuerdos} />
    </li>
  )
}

// Un acuerdo se considera cerrado/cumplido con estos status (backend: Compromiso).
const ACUERDO_CERRADO = new Set(["completado", "cerrado", "cumplido"])

/** Fecha ISO (YYYY-MM-DD) → "15 mar 2026" en es-MX; "" si no viene o es inválida. */
function formatFechaEsMX(iso: string | null): string {
  if (!iso) return ""
  const d = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(d.getTime())) return ""
  return d.toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" })
}

/**
 * Los acuerdos del Consejo para este punto. Se generan cuando el Consejo sesiona
 * la prioridad; si aún no hay, un texto sutil lo explica. Tolerante a defaults.
 */
function AcuerdosDelPunto({ acuerdos }: { acuerdos: AcuerdoPunto[] }) {
  const lista = (acuerdos ?? []).filter(a => a?.descripcion?.trim())

  return (
    <div className="border-t border-gray-100 p-4">
      <p className="mb-2 inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: NAVY }}>
        <Handshake className="h-3.5 w-3.5" /> Acuerdos del Consejo
      </p>
      {lista.length > 0 ? (
        <ul className="space-y-2">
          {lista.map((a, j) => {
            const cerrado = ACUERDO_CERRADO.has((a.status ?? "").toLowerCase())
            const chipColor = cerrado ? TEAL : AMBER
            const responsable = a.responsable?.trim() || ""
            const fecha = formatFechaEsMX(a.fecha_compromiso)
            return (
              <li key={j} className="rounded-lg border border-gray-100 bg-white p-3">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-xs leading-relaxed text-gray-700">{a.descripcion}</p>
                  <span
                    className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                    style={{ color: chipColor, background: `${chipColor}14` }}
                  >
                    {a.status || "abierto"}
                  </span>
                </div>
                {(responsable || fecha) && (
                  <p className="mt-1.5 flex flex-wrap items-center gap-x-1.5 text-[11px] text-gray-500">
                    {responsable && <span className="font-medium text-gray-600">{responsable}</span>}
                    {responsable && fecha && <span className="text-gray-300">·</span>}
                    {fecha && <span className="tabular-nums">{fecha}</span>}
                  </p>
                )}
              </li>
            )
          })}
        </ul>
      ) : (
        <p className="text-xs italic text-gray-400">
          Los acuerdos se generan cuando el Consejo sesiona este punto.
        </p>
      )}
    </div>
  )
}

/**
 * El análisis del punto en el formato fijo del PDF: 6 filas. Tolerante a que
 * `analisis` venga en default (todo en 0 / ""): en ese caso la decisión cae al
 * texto genérico de siempre.
 */
function AnalisisDelPunto({ analisis }: { analisis?: AnalisisPunto }) {
  const esperaba = analisis?.que_se_esperaba
  const ocurrio = analisis?.que_ocurrio
  const evidencia = analisis?.evidencia
  const desviacion = analisis?.desviacion

  const metaEsperada = esperaba?.meta?.trim() || ""
  const tareasPlaneadas = esperaba?.tareas_planeadas ?? 0
  const hechas = ocurrio?.hechas ?? 0
  const enProceso = ocurrio?.en_proceso ?? 0
  const pendientes = ocurrio?.pendientes ?? 0
  const kpis = (ocurrio?.kpis ?? []) as Array<Record<string, unknown>>
  const documentosSubidos = evidencia?.documentos_subidos ?? 0
  const tareasVencidas = desviacion?.tareas_vencidas ?? 0
  const kpisSinDato = desviacion?.kpis_sin_dato ?? 0
  const hayDesviacion = tareasVencidas > 0 || kpisSinDato > 0
  const desviacionColor = hayDesviacion ? AMBER : TEAL

  const decision = analisis?.decision_sugerida?.trim()
    || "Revisar el avance del periodo y decidir si la prioridad continúa, se ajusta la meta o se corrige el rumbo."

  const filaLabel = (icon: ReactNode, text: string) => (
    <p className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400">
      {icon} {text}
    </p>
  )

  return (
    <div className="border-t border-gray-100 p-4" style={{ background: "#fbfcfe" }}>
      <p className="mb-3 inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: NAVY }}>
        <Scale className="h-3.5 w-3.5" /> Análisis del punto
      </p>

      <dl className="space-y-3">
        {/* 1 · Qué se esperaba */}
        <div>
          {filaLabel(<Target className="h-3.5 w-3.5" />, "Qué se esperaba")}
          <p className="mt-1 text-xs leading-relaxed text-gray-700">
            {metaEsperada ? <>Meta: <span className="font-medium">{metaEsperada}</span> · </> : null}
            <span className="tabular-nums">{tareasPlaneadas}</span> tarea{tareasPlaneadas === 1 ? "" : "s"} planeada{tareasPlaneadas === 1 ? "" : "s"}
          </p>
        </div>

        {/* 2 · Qué ocurrió */}
        <div>
          {filaLabel(<ListChecks className="h-3.5 w-3.5" />, "Qué ocurrió")}
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <Chip color={TEAL}>{hechas} hechas</Chip>
            <Chip color={NAVY}>{enProceso} en proceso</Chip>
            <Chip color={pendientes > 0 ? AMBER : "#64748b"}>{pendientes} pendientes</Chip>
          </div>
          {kpis.length > 0 && (
            <ul className="mt-2 space-y-1">
              {kpis.map((k, j) => {
                const label = String(k.label ?? "")
                const actual = String(k.actual ?? "").trim()
                const kmeta = String(k.meta ?? "").trim()
                if (!label) return null
                return (
                  <li key={j} className="text-xs leading-snug text-gray-600">
                    {label}:{" "}
                    <span className="text-gray-500">{actual || "—"}</span>
                    <span className="mx-1 text-gray-300">→</span>
                    <span className="font-semibold" style={{ color: TEAL }}>{kmeta || "por definir"}</span>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {/* 3 · Evidencia */}
        <div>
          {filaLabel(<FileText className="h-3.5 w-3.5" />, "Evidencia")}
          <p className="mt-1 text-xs leading-relaxed text-gray-700">
            <span className="font-medium tabular-nums">{documentosSubidos}</span> documento{documentosSubidos === 1 ? "" : "s"} subido{documentosSubidos === 1 ? "" : "s"}
          </p>
        </div>

        {/* 4 · Desviación */}
        <div>
          {filaLabel(<AlertTriangle className="h-3.5 w-3.5" />, "Desviación")}
          <p className="mt-1 inline-flex items-center gap-1.5 text-xs font-medium leading-relaxed" style={{ color: desviacionColor }}>
            {hayDesviacion ? <AlertTriangle className="h-3.5 w-3.5" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
            <span className="tabular-nums">{tareasVencidas}</span> tarea{tareasVencidas === 1 ? "" : "s"} vencida{tareasVencidas === 1 ? "" : "s"}
            <span className="text-gray-300">·</span>
            <span className="tabular-nums">{kpisSinDato}</span> indicador{kpisSinDato === 1 ? "" : "es"} sin dato
          </p>
        </div>

        {/* 5 · Explicación de la administración (placeholder) */}
        <div>
          {filaLabel(<ClipboardList className="h-3.5 w-3.5" />, "Explicación de la administración")}
          <p className="mt-1 text-xs italic leading-relaxed text-gray-400">Se documenta durante la sesión.</p>
        </div>

        {/* 6 · Qué decide el Consejo */}
        <div className="flex items-start gap-2.5 rounded-lg border border-gray-100 bg-white p-3">
          <Gavel className="mt-0.5 h-4 w-4 shrink-0" style={{ color: NAVY }} />
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400">Qué decide el Consejo</p>
            <p className="mt-0.5 text-xs leading-relaxed text-gray-700">{decision}</p>
          </div>
        </div>
      </dl>
    </div>
  )
}

function Chip({ color, children }: { color: string; children: ReactNode }) {
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums"
      style={{ color, background: `${color}14` }}
    >
      {children}
    </span>
  )
}
