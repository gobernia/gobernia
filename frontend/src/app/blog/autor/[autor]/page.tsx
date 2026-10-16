import type { Metadata } from "next"
import Image from "next/image"
import { notFound } from "next/navigation"
import JsonLd from "@/components/blog/JsonLd"
import TarjetaArticulo from "@/components/blog/TarjetaArticulo"
import { B, SANS } from "@/components/blog/tokens"
import { AUTORES, getArticulos, resumen } from "@/lib/blog"
import { SITE_NAME, SITE_URL } from "@/lib/seo"

export const dynamicParams = false

export function generateStaticParams() {
  return Object.keys(AUTORES).map(autor => ({ autor }))
}

type Props = { params: Promise<{ autor: string }> }

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const au = AUTORES[(await params).autor]
  if (!au) return {}
  return {
    title: `${au.nombre}, ${au.cargo} — ${SITE_NAME}`,
    description: au.bio.slice(0, 155),
    alternates: { canonical: `/blog/autor/${au.slug}` },
  }
}

export default async function AutorPage({ params }: Props) {
  const au = AUTORES[(await params).autor]
  if (!au) notFound()
  const articulos = getArticulos().filter(a => a.autor.slug === au.slug).map(resumen)

  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org",
        "@type": "ProfilePage",
        url: `${SITE_URL}/blog/autor/${au.slug}`,
        mainEntity: {
          "@type": "Person",
          "@id": `${SITE_URL}/blog/autor/${au.slug}#persona`,
          name: au.nombre,
          jobTitle: au.cargo,
          description: au.bio,
          image: `${SITE_URL}${au.foto}`,
          worksFor: { "@type": "Organization", name: au.organizacion.nombre, url: au.organizacion.url },
          sameAs: au.sameAs,
        },
      }} />
      <section className="px-[var(--px-fluid)] pt-14 sm:pt-20">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto flex flex-col sm:flex-row gap-8 items-start">
          <Image src={au.foto} alt={au.nombre} width={160} height={160} priority className="h-40 w-40 shrink-0 rounded-[26px] object-cover" />
          <div className="max-w-[42em]">
            <p className="text-[11px] font-extrabold uppercase tracking-[0.16em]" style={{ ...SANS, color: B.ACCENT }}>Autor</p>
            <h1 className="mt-3" style={{ ...SANS, color: B.BNAVY, fontWeight: 700, fontSize: "clamp(30px, 4vw, 52px)", lineHeight: 1.06, letterSpacing: "-0.03em" }}>
              {au.nombre}
            </h1>
            <p className="mt-2 text-[16px] font-medium" style={{ color: B.INK2 }}>{au.cargo}</p>
            <p className="mt-4 text-[16px] leading-relaxed" style={{ color: B.INK2 }}>{au.bio}</p>
          </div>
        </div>
      </section>
      <section className="px-[var(--px-fluid)] mt-14">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto">
          <h2 style={{ ...SANS, color: B.BNAVY, fontWeight: 700, fontSize: 26, letterSpacing: "-0.02em" }}>
            Artículos de {au.nombre} ({articulos.length})
          </h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {articulos.map(a => <TarjetaArticulo key={a.slug} a={a} />)}
          </div>
        </div>
      </section>
    </>
  )
}
