"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { Loader2, Download, BadgeCheck, FileText, Library } from "lucide-react"
import { PageShell, PageHeader, Prose } from "@/components/ui/PageShell"
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
      <PageHeader eyebrow="Documentos validados" title="Biblioteca" />

      <main>
        <PageShell className="py-10 space-y-6">
          <Prose>
            <p className="text-sm text-gray-500 leading-relaxed">
              Aquí se guardan los documentos que validaste. Quedan registrados para tus sesiones de consejo
              y puedes descargarlos cuando los necesites.
            </p>
          </Prose>

          {docs === null && (
            <div className="border border-gray-100 rounded-2xl p-16 flex items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-gray-300" />
            </div>
          )}

          {docs !== null && docs.length === 0 && (
            <div className="border border-gray-100 rounded-2xl p-12 sm:p-16 flex flex-col items-center text-center gap-4">
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
                className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-5 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
                Ir a mi Roadmap
              </Link>
            </div>
          )}

          {docs !== null && docs.length > 0 && (
            <div className="grid gap-4 items-start sm:grid-cols-2 xl:grid-cols-3">
              {docs.map((d, i) => (
                <motion.article key={d.tipo} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, ease: EASE, delay: i * 0.05 }}
                  className="group flex h-full flex-col overflow-hidden rounded-2xl border border-gray-100 transition-colors hover:border-[var(--gob-navy)]/30">

                  {/* Lomo del documento: la tarjeta se lee como una hoja, no como una fila */}
                  <div className="flex h-28 items-center justify-center border-b border-gray-100 bg-[var(--gob-paper)]">
                    <span className="flex h-14 w-11 items-center justify-center rounded-md border border-[var(--gob-rule)] bg-white text-[var(--gob-navy)] shadow-sm">
                      <FileText className="h-5 w-5" />
                    </span>
                  </div>

                  <div className="flex flex-1 flex-col gap-3 p-5">
                    <div className="space-y-1.5">
                      <h2 className="text-sm font-bold tracking-tight text-black">{d.titulo}</h2>
                      <p className="text-xs leading-relaxed text-gray-500">{d.descripcion}</p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2.5 py-0.5 text-[11px] font-medium text-green-700">
                        <BadgeCheck className="h-3 w-3" /> Validado{fecha(d.validado_at) ? ` · ${fecha(d.validado_at)}` : ""}
                      </span>
                      {d.estado && (
                        <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-[11px] text-amber-700">{d.estado}</span>
                      )}
                    </div>

                    <button onClick={() => onDownload(d)} disabled={downloading === d.tipo}
                      className="mt-auto inline-flex items-center justify-center gap-2 rounded-xl border border-gray-200 px-3.5 py-2.5 text-sm font-medium text-gray-700 transition-colors hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
                      {downloading === d.tipo ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                      Descargar PDF
                    </button>
                  </div>
                </motion.article>
              ))}
            </div>
          )}
        </PageShell>
      </main>
    </div>
  )
}
