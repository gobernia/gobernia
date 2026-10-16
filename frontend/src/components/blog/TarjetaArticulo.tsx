import Link from "next/link"
import type { ArticuloResumen } from "@/lib/blog"
import { slugCategoria } from "@/lib/blog"
import { B, SANS } from "./tokens"

export default function TarjetaArticulo({ a, destacado = false }: { a: ArticuloResumen; destacado?: boolean }) {
  return (
    <article
      className="group relative h-full flex flex-col rounded-[26px] p-6 sm:p-7 transition-shadow hover:shadow-[0_8px_30px_-12px_rgba(14,22,38,.25)]"
      style={{ background: destacado ? B.BNAVY : B.CARD, border: `1px solid ${destacado ? B.BNAVY : B.LINE}` }}>
      <Link href={`/blog/categoria/${slugCategoria(a.categoria)}`}
        className="relative z-10 self-start text-[11px] font-extrabold uppercase tracking-[0.12em] hover:underline"
        style={{ ...SANS, color: destacado ? "#F5B08C" : B.ACCENT }}>
        {a.categoria}
      </Link>
      <h3 className={`mt-3 font-bold leading-snug tracking-[-0.02em] ${destacado ? "text-[26px] sm:text-[30px]" : "text-[19px]"}`}
        style={{ ...SANS, color: destacado ? "#FFFFFF" : B.INK }}>
        <Link href={`/blog/${a.slug}`} className="after:absolute after:inset-0 after:rounded-[26px]">
          {a.titulo}
        </Link>
      </h3>
      <p className={`mt-3 leading-relaxed flex-1 ${destacado ? "text-[15.5px]" : "text-[14px]"}`}
        style={{ color: destacado ? "rgba(255,255,255,.78)" : B.INK2 }}>
        {a.descripcion}
      </p>
      <p className="mt-5 text-xs" style={{ color: destacado ? "rgba(255,255,255,.6)" : B.MUTED }}>
        {a.autor.nombre} · {a.minutos} min de lectura
      </p>
    </article>
  )
}
