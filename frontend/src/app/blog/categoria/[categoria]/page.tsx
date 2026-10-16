import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"
import JsonLd from "@/components/blog/JsonLd"
import TarjetaArticulo from "@/components/blog/TarjetaArticulo"
import { B, SANS } from "@/components/blog/tokens"
import { categoriaPorSlug, categoriasConArticulos, getArticulos, resumen } from "@/lib/blog"
import { SITE_NAME, SITE_URL } from "@/lib/seo"

export const dynamicParams = false

export function generateStaticParams() {
  return categoriasConArticulos().map(c => ({ categoria: c.slug }))
}

type Props = { params: Promise<{ categoria: string }> }

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const c = categoriaPorSlug((await params).categoria)
  if (!c) return {}
  const titulo = `${c.nombre}: artículos para dueños y consejeros`
  const descripcion = `${c.total} artículos de Fernando Todd sobre ${c.nombre.toLowerCase()} en empresas familiares: conceptos, casos y prácticas de gobierno corporativo.`
  return {
    title: `${titulo} — ${SITE_NAME}`,
    description: descripcion,
    alternates: { canonical: `/blog/categoria/${c.slug}` },
    openGraph: { title: titulo, description: descripcion, url: `/blog/categoria/${c.slug}`, type: "website", locale: "es_MX", siteName: SITE_NAME },
  }
}

export default async function CategoriaPage({ params }: Props) {
  const c = categoriaPorSlug((await params).categoria)
  if (!c) notFound()
  const articulos = getArticulos().filter(a => a.categoria === c.nombre).map(resumen)

  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org",
        "@graph": [
          {
            "@type": "CollectionPage",
            name: `${c.nombre} | Blog de ${SITE_NAME}`,
            url: `${SITE_URL}/blog/categoria/${c.slug}`,
            inLanguage: "es-MX",
            isPartOf: { "@id": `${SITE_URL}/blog#blog` },
            hasPart: articulos.map(a => ({ "@type": "BlogPosting", headline: a.titulo, url: `${SITE_URL}/blog/${a.slug}` })),
          },
          {
            "@type": "BreadcrumbList",
            itemListElement: [
              { "@type": "ListItem", position: 1, name: "Inicio", item: `${SITE_URL}/` },
              { "@type": "ListItem", position: 2, name: "Blog", item: `${SITE_URL}/blog` },
              { "@type": "ListItem", position: 3, name: c.nombre, item: `${SITE_URL}/blog/categoria/${c.slug}` },
            ],
          },
        ],
      }} />

      <section className="px-[var(--px-fluid)] pt-14 sm:pt-20 pb-10">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto">
          <nav aria-label="Ruta" className="text-[13px]" style={{ color: B.MUTED }}>
            <Link href="/blog" className="hover:text-[#152742]">Blog</Link> <span aria-hidden>/</span> {c.nombre}
          </nav>
          <h1 className="mt-4" style={{ ...SANS, color: B.BNAVY, fontWeight: 700, fontSize: "clamp(30px, 4vw, 56px)", lineHeight: 1.06, letterSpacing: "-0.03em" }}>
            {c.nombre}
          </h1>
          <p className="mt-4 text-[16px] leading-relaxed max-w-[40em]" style={{ color: B.INK2 }}>
            {c.total} {c.total === 1 ? "artículo" : "artículos"} sobre {c.nombre.toLowerCase()} para dueños, familias empresarias y consejeros.
          </p>
        </div>
      </section>

      <section className="px-[var(--px-fluid)]">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {articulos.map(a => <TarjetaArticulo key={a.slug} a={a} />)}
        </div>
      </section>
    </>
  )
}
