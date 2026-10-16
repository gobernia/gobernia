"use client"

// Carrusel de artículos del blog en la home: desliza con el dedo o el trackpad (scroll-snap)
// y con las flechas en escritorio. Los enlaces van en el HTML, así que Google los rastrea.
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"
import Link from "next/link"
import { ArrowLeft, ArrowRight } from "lucide-react"
import { B, SANS } from "@/components/blog/tokens"

export interface ArticuloCarrusel {
  slug: string
  titulo: string
  descripcion: string
  categoria: string
  autor: string
  minutos: number
}

export default function CarruselBlog({ articulos, encabezado }: { articulos: ArticuloCarrusel[]; encabezado: ReactNode }) {
  const pista = useRef<HTMLDivElement>(null)
  const [bordes, setBordes] = useState({ inicio: true, fin: false })

  const medir = useCallback(() => {
    const el = pista.current
    if (!el) return
    setBordes({ inicio: el.scrollLeft < 8, fin: el.scrollLeft + el.clientWidth >= el.scrollWidth - 8 })
  }, [])

  useEffect(() => {
    medir()
    window.addEventListener("resize", medir)
    return () => window.removeEventListener("resize", medir)
  }, [medir])

  // Avanza casi una pantalla de tarjetas, dejando ver la siguiente.
  const mover = (dir: 1 | -1) => {
    const el = pista.current
    if (el) el.scrollBy({ left: dir * el.clientWidth * 0.85, behavior: "smooth" })
  }

  const flecha = "h-11 w-11 inline-flex items-center justify-center rounded-full transition-colors disabled:opacity-35"

  return (
    <div aria-roledescription="carrusel" aria-label="Artículos del blog">
      <div className="flex items-end justify-between gap-6">
        <div className="min-w-0">{encabezado}</div>
        <div className="hidden sm:flex gap-2 shrink-0">
          <button type="button" aria-label="Artículos anteriores" onClick={() => mover(-1)} disabled={bordes.inicio}
            className={`${flecha} hover:bg-white`} style={{ border: `1px solid ${B.LINE}`, color: B.BNAVY }}>
            <ArrowLeft className="h-4 w-4" />
          </button>
          <button type="button" aria-label="Más artículos" onClick={() => mover(1)} disabled={bordes.fin}
            className={`${flecha} text-white hover:brightness-90`} style={{ background: B.BNAVY }}>
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div ref={pista} onScroll={medir}
        className="sin-barra carrusel-sangre mt-10 flex gap-5 overflow-x-auto snap-x snap-mandatory scroll-smooth pb-2">
        {articulos.map(a => (
          <article key={a.slug}
            className="group relative snap-start shrink-0 w-[84%] sm:w-[46%] lg:w-[31.5%] 2xl:w-[23.6%] flex flex-col rounded-[26px] p-6 sm:p-7 transition-shadow hover:shadow-[0_8px_30px_-12px_rgba(14,22,38,.25)]"
            style={{ background: B.CARD, border: `1px solid ${B.LINE}` }}>
            <p className="text-[11px] font-extrabold uppercase tracking-[0.12em]" style={{ ...SANS, color: B.ACCENT }}>{a.categoria}</p>
            <h3 className="mt-3 text-[19px] font-bold leading-snug tracking-[-0.02em]" style={{ ...SANS, color: B.INK }}>
              <Link href={`/blog/${a.slug}`} className="after:absolute after:inset-0 after:rounded-[26px]">{a.titulo}</Link>
            </h3>
            <p className="mt-3 flex-1 text-[14px] leading-relaxed" style={{ color: B.INK2 }}>{a.descripcion}</p>
            <p className="mt-5 text-xs" style={{ color: B.MUTED }}>{a.autor} · {a.minutos} min de lectura</p>
          </article>
        ))}
        <Link href="/blog"
          className="snap-start shrink-0 w-[84%] sm:w-[46%] lg:w-[31.5%] 2xl:w-[23.6%] flex flex-col justify-between rounded-[26px] p-6 sm:p-7 text-white transition-colors hover:brightness-110"
          style={{ background: B.BNAVY }}>
          <p className="text-[11px] font-extrabold uppercase tracking-[0.12em]" style={{ ...SANS, color: "#F5B08C" }}>Blog</p>
          <div>
            <p className="text-[24px] font-bold leading-tight tracking-[-0.02em]" style={SANS}>Ver todos los artículos</p>
            <p className="mt-3 text-[14px] leading-relaxed" style={{ color: "rgba(255,255,255,.75)" }}>
              Gobierno corporativo, Consejo de Administración, sucesión, protocolo familiar y finanzas.
            </p>
          </div>
          <span className="mt-6 inline-flex h-11 w-11 items-center justify-center rounded-full bg-white" style={{ color: B.BNAVY }}>
            <ArrowRight className="h-4 w-4" />
          </span>
        </Link>
      </div>
    </div>
  )
}
