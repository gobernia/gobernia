"use client"

import { BadgeCheck, Download, Loader2 } from "lucide-react"

/** Cabecera fija del expediente: qué documento es, en qué estado está y qué puedes hacer con él. */
export default function RoadmapHeader({
  anios, anioObjetivo, listo, validado, validando, downloading, onDownload, onValidar,
}: {
  anios: number
  anioObjetivo?: number
  /** El roadmap ya tiene contenido: se pueden ofrecer las acciones. */
  listo: boolean
  validado: boolean
  validando: boolean
  downloading: boolean
  onDownload: () => void
  onValidar: () => void
}) {
  return (
    <div className="sticky top-0 z-30 border-b border-[var(--gob-rule)] bg-white/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-3 px-[var(--px-fluid)] py-3.5">
        <div className="min-w-0">
          <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-[var(--gob-stone)]">
            Documento del consejo · plan a {anios} años
          </p>
          <div className="flex items-center gap-2.5">
            <h1 className="truncate text-lg font-bold tracking-tight text-[var(--gob-ink)] sm:text-xl">
              Roadmap estratégico{anioObjetivo ? ` al ${anioObjetivo}` : ""}
            </h1>
            {listo && (
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.14em] ${
                validado
                  ? "bg-green-100 text-green-700"
                  : "border border-dashed border-[var(--gob-navy)]/35 text-[var(--gob-navy)]"}`}>
                {validado ? "Validado" : "Borrador"}
              </span>
            )}
          </div>
        </div>

        {listo && (
          <div className="flex shrink-0 items-center gap-2">
            <button onClick={onDownload} disabled={downloading}
              className="inline-flex items-center gap-2 rounded-xl border border-[var(--gob-rule)] px-3.5 py-2.5 text-sm font-medium text-[var(--gob-charcoal)] transition-colors hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
              {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              PDF
            </button>
            {!validado && (
              <button onClick={onValidar} disabled={validando}
                className="inline-flex items-center gap-2 rounded-xl bg-[var(--gob-navy)] px-4 py-2.5 text-sm font-medium text-[var(--gob-bone)] transition-colors hover:bg-[var(--gob-ink)] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
                {validando ? <Loader2 className="h-4 w-4 animate-spin" /> : <BadgeCheck className="h-4 w-4" />}
                Validar
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
