/**
 * Sistema de ancho del dashboard.
 *
 * Una sola medida para TODAS las páginas: el lienzo llega a 1440px y respira con
 * `--px-fluid`. Lo que cambia entre pantallas no es el ancho del lienzo, sino cómo se
 * reparte el contenido dentro de él (rejillas, columnas).
 *
 * `Prose` existe porque un párrafo de 1400px es ilegible: el texto corrido se mantiene
 * en un ancho de lectura cómodo AUNQUE viva dentro del lienzo ancho.
 */
import type { ReactNode } from "react"

/** Lienzo de la página. Úsalo en el <main> y también en el header sticky, para que alineen. */
export function PageShell({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`mx-auto w-full max-w-[1440px] px-[var(--px-fluid)] ${className}`}>
      {children}
    </div>
  )
}

/** Ancho de lectura para texto corrido (~72 caracteres). */
export function Prose({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`max-w-[68ch] ${className}`}>{children}</div>
}

/** Encabezado sticky estándar: eyebrow + título + acciones a la derecha. */
export function PageHeader({
  eyebrow, title, actions,
}: { eyebrow?: string; title: string; actions?: ReactNode }) {
  return (
    <div className="sticky top-0 z-20 bg-white/90 backdrop-blur-md border-b border-gray-100">
      <PageShell className="py-3.5 flex items-center justify-between gap-4 flex-wrap">
        <div className="min-w-0">
          {eyebrow && (
            <p className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">{eyebrow}</p>
          )}
          <h1 className="text-lg sm:text-xl font-bold tracking-tight truncate">{title}</h1>
        </div>
        {actions && <div className="flex items-center gap-2 flex-wrap">{actions}</div>}
      </PageShell>
    </div>
  )
}
