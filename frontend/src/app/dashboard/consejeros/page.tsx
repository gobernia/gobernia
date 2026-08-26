"use client"

// MIS CONSEJEROS — quiénes son los cinco consejeros del Consejo y el
// repositorio de documentos que los alimenta: aquí el usuario sube estados
// financieros, organigramas, planes, etc., para que los análisis tengan
// mejor materia prima. (Las tarjetas vivían en Board IA; ahora tienen casa propia.)

import { useEffect, useRef, useState, type CSSProperties } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, Loader2, Upload, FileText, Trash2, CheckCircle2, Clock, Play } from "lucide-react"
import { PageShell, PageHeader, Prose } from "@/components/ui/PageShell"
import { getDocumentos, subirDocumento, eliminarDocumento, type DocumentoRepo, type TipoDocumento } from "@/lib/documentos"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

// Paleta bento — mismos tokens del resto del dashboard.
const INK   = "#0E1626"
const INK2  = "#39435A"
const MUTED = "#6E7686"
const CARD  = "#FFFFFF"
const SAND  = "#E8E3D8"
const BNAVY = "#152742"
const ACCENT = "#C2410C"
const LINE  = "#E2E2DC"
const SANS: CSSProperties = { fontFamily: "var(--font-sans)" }

const AGENTS = [
  { tag: "Consejero en", name: "Finanzas",      desc: "Rentabilidad, flujo de caja y estructura de capital.", docs: "Estados financieros" },
  { tag: "Consejero en", name: "Estrategia",    desc: "Posicionamiento, mercado y crecimiento a largo plazo.", docs: "Plan de negocios y presentaciones" },
  { tag: "Consejero en", name: "Riesgos",       desc: "Riesgos operativos, legales y planes de mitigación.", docs: "Actas, estatutos y reglamentos" },
  { tag: "Consejero en", name: "Auditoría",     desc: "Cumplimiento, control interno y Governance Score.", docs: "Planes de auditoría y reglamentos" },
  { tag: "Consejero",    name: "Independiente", desc: "El Retador: cuestiona cada decisión con un pre-mortem antes de actuar.", docs: "Lee el contexto completo" },
]

export default function ConsejerosPage() {
  const [docs, setDocs] = useState<DocumentoRepo[]>([])
  const [tipos, setTipos] = useState<TipoDocumento[]>([])
  const [loaded, setLoaded] = useState(false)
  const [tipoSel, setTipoSel] = useState("financial")
  const [subiendo, setSubiendo] = useState(false)
  const [borrando, setBorrando] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    getDocumentos()
      .then(({ items, types }) => {
        if (!aliveRef.current) return
        setDocs(items)
        setTipos(types)
      })
      .catch(() => {})
      .finally(() => { if (aliveRef.current) setLoaded(true) })
    return () => { aliveRef.current = false }
  }, [])

  const onFile = async (f: File | null) => {
    if (!f || subiendo) return
    setSubiendo(true)
    setError(null)
    try {
      await subirDocumento(f, tipoSel)
      const { items } = await getDocumentos()
      if (aliveRef.current) setDocs(items)
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      if (aliveRef.current) setError(typeof detail === "string" ? detail : "No se pudo subir el documento. Intenta de nuevo.")
    } finally {
      if (aliveRef.current) setSubiendo(false)
      if (fileRef.current) fileRef.current.value = ""
    }
  }

  const borrar = async (id: string) => {
    if (borrando) return
    if (!window.confirm("¿Eliminar este documento? Tus consejeros dejarán de usarlo.")) return
    setBorrando(id)
    try {
      await eliminarDocumento(id)
      if (aliveRef.current) setDocs(prev => prev.filter(d => d.document_id !== id))
    } catch {
      if (aliveRef.current) setError("No se pudo eliminar el documento.")
    } finally {
      if (aliveRef.current) setBorrando(null)
    }
  }

  return (
    <div className="min-h-dvh font-sans antialiased" style={{ background: "#F2F2F0", color: INK }}>
      <PageHeader eyebrow="Tu Consejo de Administración" title="Mis consejeros" />

      <main>
        <PageShell className="py-10 space-y-12">

          {/* ── Los cinco consejeros ─────────────────────── */}
          <section className="space-y-5">
            <Prose>
              <p className="text-sm leading-relaxed" style={{ color: INK2 }}>
                Cada consejero analiza tu empresa desde su especialidad y deja por escrito sus
                hallazgos, alertas y preguntas para la junta. Puedes conversar con cualquiera de
                ellos dentro de una Sesión de Consejo.
              </p>
            </Prose>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
              {AGENTS.map((a, i) => (
                <motion.div key={a.name} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, ease: EASE, delay: 0.05 + i * 0.07 }}
                  className="rounded-[26px] p-6 flex flex-col gap-3 transition-all duration-300 hover:shadow-sm"
                  style={{ background: CARD, border: `1px solid ${LINE}` }}>
                  <div>
                    <p className="text-xs" style={{ color: MUTED }}>{a.tag}</p>
                    <p className="text-base font-bold mt-0.5" style={{ ...SANS, color: INK }}>{a.name}</p>
                  </div>
                  <p className="text-xs leading-relaxed flex-1" style={{ color: INK2 }}>{a.desc}</p>
                  <p className="text-[11px] font-semibold leading-snug border-t pt-2.5" style={{ color: MUTED, borderColor: LINE }}>
                    <span className="font-extrabold uppercase tracking-[0.08em]" style={{ color: ACCENT }}>Lee</span>{" "}
                    {a.docs}
                  </p>
                  <Link
                    href="/dashboard/consejo?sesionar=1"
                    className="flex w-full items-center justify-between rounded-[20px] px-3 py-2.5 text-xs font-medium transition-all duration-150"
                    style={{ border: `1px solid ${LINE}`, color: INK2 }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = BNAVY; e.currentTarget.style.color = BNAVY }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = LINE; e.currentTarget.style.color = INK2 }}
                  >
                    Iniciar sesión
                    <Play className="h-3 w-3" />
                  </Link>
                </motion.div>
              ))}
            </div>
          </section>

          {/* ── Documentos para tus consejeros ───────────── */}
          <section className="space-y-5">
            <div>
              <p className="text-xs font-medium tracking-widest uppercase mb-1" style={{ color: MUTED }}>Documentos</p>
              <h2 className="text-2xl font-bold tracking-tight" style={{ ...SANS, color: INK }}>Alimenta a tu Consejo</h2>
              <p className="text-sm leading-relaxed mt-2 max-w-[68ch]" style={{ color: INK2 }}>
                Sube aquí los documentos de tu empresa (estados financieros, organigrama, plan de
                negocios…). Tus consejeros los leen y sus análisis mejoran con cada documento.
              </p>
            </div>

            {/* Subida: tipo + archivo */}
            <div className="rounded-[26px] p-6 space-y-4" style={{ background: SAND }}>
              <div className="flex flex-wrap items-end gap-4">
                <label className="block">
                  <span className="mb-1.5 block text-[10px] font-extrabold uppercase tracking-[0.16em]" style={{ ...SANS, color: MUTED }}>
                    Tipo de documento
                  </span>
                  <select
                    value={tipoSel}
                    onChange={e => setTipoSel(e.target.value)}
                    className="rounded-[12px] px-3 py-2.5 text-sm focus-visible:outline-none focus-visible:ring-2"
                    style={{ background: CARD, border: `1px solid ${LINE}`, color: INK }}
                  >
                    {(tipos.length > 0 ? tipos : [{ value: "financial", label: "Estados financieros" }]).map(t => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </label>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv"
                  className="hidden"
                  onChange={e => onFile(e.target.files?.[0] ?? null)}
                />
                <button
                  type="button"
                  onClick={() => fileRef.current?.click()}
                  disabled={subiendo}
                  className="inline-flex items-center gap-2.5 rounded-full px-5 py-2.5 text-[13px] font-bold text-white transition-colors hover:brightness-90 disabled:opacity-50"
                  style={{ ...SANS, background: BNAVY }}
                >
                  {subiendo ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                  {subiendo ? "Subiendo…" : "Subir documento"}
                </button>
                <p className="text-xs" style={{ color: MUTED }}>PDF, Word, Excel o PowerPoint · máx. 10 MB</p>
              </div>
              {error && <p className="text-xs" style={{ color: "#dc2626" }}>{error}</p>}
            </div>

            {/* Lista de documentos */}
            {!loaded ? (
              <div className="flex items-center justify-center rounded-[26px] p-12" style={{ background: CARD, border: `1px solid ${LINE}` }}>
                <Loader2 className="h-5 w-5 animate-spin" style={{ color: MUTED }} />
              </div>
            ) : docs.length > 0 ? (
              <ul className="overflow-hidden rounded-[26px]" style={{ border: `1px solid ${LINE}` }}>
                {docs.map(d => (
                  <li key={d.document_id} className="flex flex-wrap items-center gap-3 px-5 py-3.5"
                    style={{ background: CARD, borderBottom: `1px solid ${LINE}` }}>
                    <FileText className="h-4 w-4 shrink-0" style={{ color: BNAVY }} />
                    <span className="min-w-0 flex-1 text-sm leading-snug" style={{ color: INK }}>
                      {d.filename}
                      <span className="ml-2 text-[11px] font-semibold" style={{ color: MUTED }}>· {d.document_type_label}</span>
                    </span>
                    <span className="inline-flex items-center gap-1.5 text-[11px] font-bold" style={{ color: d.status === "completed" ? "#0f766e" : MUTED }}>
                      {d.status === "completed" ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Clock className="h-3.5 w-3.5" />}
                      {d.status === "completed" ? "Listo" : "Procesándose"}
                    </span>
                    <button
                      type="button"
                      onClick={() => borrar(d.document_id)}
                      disabled={borrando !== null}
                      aria-label={`Eliminar ${d.filename}`}
                      className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
                      style={{ border: `1px solid ${LINE}`, color: MUTED }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = "#b91c1c"; e.currentTarget.style.color = "#b91c1c" }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = LINE; e.currentTarget.style.color = MUTED }}
                    >
                      {borrando === d.document_id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                      Eliminar
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="flex flex-col items-center gap-3 rounded-[26px] p-10 text-center" style={{ background: CARD, border: `1px solid ${LINE}` }}>
                <FileText className="h-6 w-6" style={{ color: MUTED }} />
                <p className="text-sm font-medium" style={{ ...SANS, color: INK }}>Aún no hay documentos</p>
                <p className="max-w-md text-sm leading-relaxed" style={{ color: INK2 }}>
                  Sube el primero para que tus consejeros trabajen con los números y documentos
                  reales de tu empresa.
                </p>
              </div>
            )}

            <Link
              href="/dashboard/consejo"
              className="inline-flex items-center gap-2.5 rounded-full px-5 py-3 text-[13px] font-bold tracking-wide text-white transition-colors hover:brightness-90"
              style={{ ...SANS, background: ACCENT }}
            >
              Ir al Board IA <ArrowRight className="h-4 w-4" />
            </Link>
          </section>

        </PageShell>
      </main>
    </div>
  )
}
