import type { Metadata } from "next"
import Link from "next/link"
import JsonLd from "@/components/blog/JsonLd"
import TarjetaArticulo from "@/components/blog/TarjetaArticulo"
import { B, SANS } from "@/components/blog/tokens"
import { categoriasConArticulos, getArticulos, resumen } from "@/lib/blog"
import { SITE_NAME, SITE_URL } from "@/lib/seo"

const TITULO = "Blog de gobierno corporativo y empresas familiares"
const DESCRIPCION =
  "Artículos de Fernando Todd sobre gobierno corporativo, consejo de administración, sucesión, protocolo familiar y finanzas para dueños y consejeros."

export const metadata: Metadata = {
  title: `${TITULO} — ${SITE_NAME}`,
  description: DESCRIPCION,
  alternates: { canonical: "/blog" },
  openGraph: { title: TITULO, description: DESCRIPCION, url: "/blog", type: "website", locale: "es_MX", siteName: SITE_NAME },
}

export default function BlogIndex() {
  const articulos = getArticulos().map(resumen)
  const categorias = categoriasConArticulos()
  const [destacado, ...resto] = articulos

  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org",
        "@type": "Blog",
        "@id": `${SITE_URL}/blog#blog`,
        name: `${TITULO} | ${SITE_NAME}`,
        description: DESCRIPCION,
        url: `${SITE_URL}/blog`,
        inLanguage: "es-MX",
        publisher: { "@id": `${SITE_URL}/#org` },
        blogPost: articulos.map(a => ({
          "@type": "BlogPosting",
          headline: a.titulo,
          url: `${SITE_URL}/blog/${a.slug}`,
          datePublished: a.fecha,
          author: { "@type": "Person", name: a.autor.nombre },
        })),
      }} />

      <section className="px-[var(--px-fluid)] pt-14 sm:pt-20 pb-10">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto">
          <p className="text-[11px] font-extrabold uppercase tracking-[0.16em]" style={{ ...SANS, color: B.ACCENT }}>Blog</p>
          <h1 className="mt-4 max-w-[16em]" style={{ ...SANS, color: B.BNAVY, fontWeight: 300, fontSize: "clamp(32px, 4.6vw, 72px)", lineHeight: 1.04, letterSpacing: "-0.03em" }}>
            Gobierno corporativo para <strong style={{ fontWeight: 700 }}>dueños, consejos</strong> y familias empresarias.
          </h1>
          <p className="mt-6 text-[16px] sm:text-[17px] leading-relaxed max-w-[42em]" style={{ color: B.INK2 }}>{DESCRIPCION}</p>

          {categorias.length > 0 && (
            <nav aria-label="Categorías" className="mt-8 flex flex-wrap gap-2">
              {categorias.map(c => (
                <Link key={c.slug} href={`/blog/categoria/${c.slug}`}
                  className="rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors hover:text-[#152742]"
                  style={{ ...SANS, background: B.SAND, color: B.INK2 }}>
                  {c.nombre} <span style={{ color: B.MUTED }}>· {c.total}</span>
                </Link>
              ))}
            </nav>
          )}
        </div>
      </section>

      <section className="px-[var(--px-fluid)]">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto">
          {articulos.length === 0 ? (
            <p style={{ color: B.MUTED }}>Muy pronto publicaremos los primeros artículos.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              <div className="md:col-span-2 lg:col-span-2"><TarjetaArticulo a={destacado} destacado /></div>
              {resto.map(a => <TarjetaArticulo key={a.slug} a={a} />)}
            </div>
          )}
        </div>
      </section>
    </>
  )
}
