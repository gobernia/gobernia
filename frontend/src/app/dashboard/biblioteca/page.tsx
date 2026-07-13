"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { Loader2, Download, BadgeCheck, FileText, Library } from "lucide-react"
import { getBiblioteca, type DocumentoBiblioteca } from "@/lib/biblioteca"
import { downloadRoadmapPdf } from "@/lib/roadmap"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

export default function BibliotecaPage() {
  const [docs, setDocs] = useState<DocumentoBiblioteca[] | null>(null)
  const [downloading, setDownloading] = useState<string | null>(null)
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    getBiblioteca()
      .then(d => { if (aliveRef.current) setDocs(d) })
      .catch(() => { if (aliveRef.current) setDocs([]) })
    return () => { aliveRef.current = false }
  }, [])

  const onDownload = async (d: DocumentoBiblioteca) => {
    setDownloading(d.tipo)
    try {
      if (d.tipo === "roadmap") await downloadRoadmapPdf()
    } catch { /* noop */ } finally {
      if (aliveRef.current) setDownloading(null)
    }
  }

  const fecha = (iso: string | null) =>
    iso ? new Date(iso).toLocaleDateString("es-MX", { day: "numeric", month: "long", year: "numeric" }) : null

  return (
    <div className="min-h-dvh bg-white text-black">
      <div className="sticky top-0 z-20 bg-white/90 backdrop-blur-md border-b border-gray-100">
        <div className="max-w-3xl mx-auto px-[var(--px-fluid)] py-3.5">
          <p className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">Documentos validados</p>
          <h1 className="text-lg sm:text-xl font-bold tracking-tight">Biblioteca</h1>
        </div>
      </div>

      <main className="max-w-3xl mx-auto px-[var(--px-fluid)] py-10 space-y-6">
        <p className="text-sm text-gray-500 max-w-xl leading-relaxed">
          Aquí se guardan los documentos que validaste. Quedan registrados para tus sesiones de consejo
          y puedes descargarlos cuando los necesites.
        </p>

        {docs === null && (
          <div className="border border-gray-100 rounded-2xl p-16 flex items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-gray-300" />
          </div>
        )}

        {docs !== null && docs.length === 0 && (
          <div className="border border-gray-100 rounded-2xl p-12 flex flex-col items-center text-center gap-4">
            <div className="w-14 h-14 rounded-2xl border-2 border-gray-100 flex items-center justify-center">
              <Library className="h-5 w-5 text-gray-300" />
            </div>
            <div className="space-y-1.5 max-w-md">
              <p className="text-base font-medium text-black">Tu biblioteca está vacía</p>
              <p className="text-sm text-gray-500 leading-relaxed">
                Cuando valides tu Roadmap estratégico, quedará guardado aquí y registrado para tu próxima
                sesión de consejo.
              </p>
            </div>
            <Link href="/dashboard/plan"
              className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-5 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors">
              Ir a mi Roadmap
            </Link>
          </div>
        )}

        {docs !== null && docs.length > 0 && (
          <div className="space-y-3">
            {docs.map((d, i) => (
              <motion.div key={d.tipo} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, ease: EASE, delay: i * 0.05 }}
                className="rounded-2xl border border-gray-100 p-5 flex items-start gap-4">
                <span className="w-10 h-10 rounded-xl bg-[var(--gob-navy)]/[0.06] text-[var(--gob-navy)] flex items-center justify-center shrink-0">
                  <FileText className="h-5 w-5" />
                </span>
                <div className="flex-1 min-w-0 space-y-1.5">
                  <p className="text-sm font-bold text-black">{d.titulo}</p>
                  <p className="text-xs text-gray-500 leading-relaxed">{d.descripcion}</p>
                  <div className="flex flex-wrap items-center gap-2 pt-0.5">
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-green-700 bg-green-50 rounded-full px-2.5 py-0.5">
                      <BadgeCheck className="h-3 w-3" /> Validado{fecha(d.validado_at) ? ` · ${fecha(d.validado_at)}` : ""}
                    </span>
                    {d.estado && (
                      <span className="text-[11px] text-amber-700 bg-amber-50 rounded-full px-2.5 py-0.5">{d.estado}</span>
                    )}
                  </div>
                </div>
                <button onClick={() => onDownload(d)} disabled={downloading === d.tipo}
                  className="inline-flex items-center gap-2 border border-gray-200 text-sm font-medium text-gray-700 px-3.5 py-2.5 rounded-xl hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] transition-colors disabled:opacity-50 shrink-0">
                  {downloading === d.tipo ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                  PDF
                </button>
              </motion.div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
