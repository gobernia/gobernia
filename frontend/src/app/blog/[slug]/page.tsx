import type { Metadata } from "next"
import Image from "next/image"
import Link from "next/link"
import { notFound } from "next/navigation"
import { ArrowRight } from "lucide-react"
import JsonLd from "@/components/blog/JsonLd"
import TarjetaArticulo from "@/components/blog/TarjetaArticulo"
import { B, SANS } from "@/components/blog/tokens"
import { getArticulo, getArticulos, relacionados, slugCategoria } from "@/lib/blog"
import { SITE_NAME, SITE_URL } from "@/lib/seo"

export const dynamicParams = false

export function generateStaticParams() {
  return getArticulos().map(a => ({ slug: a.slug }))
}

type Props = { params: Promise<{ slug: string }> }

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const a = getArticulo((await params).slug)
  if (!a) return {}
  const url = `/blog/${a.slug}`
  return {
    title: `${a.seoTitulo} | ${SITE_NAME}`,
    description: a.descripcion,
    keywords: a.etiquetas,
    authors: [{ name: a.autor.nombre }],
    alternates: { canonical: url },
    openGraph: {
      title: a.seoTitulo,
      description: a.descripcion,
      url,
      type: "article",
      locale: "es_MX",
      siteName: SITE_NAME,
      publishedTime: a.fecha,
      authors: [a.autor.nombre],
      section: a.categoria,
      tags: a.etiquetas,
    },
    twitter: { card: "summary_large_image", title: a.seoTitulo, description: a.descripcion },
  }
}

const fechaLarga = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString("es-MX", { day: "numeric", month: "long", year: "numeric" })

export default async function ArticuloPage({ params }: Props) {
  const a = getArticulo((await params).slug)
  if (!a) notFound()
  const rel = relacionados(a)
  const url = `${SITE_URL}/blog/${a.slug}`
  const urlCategoria = `/blog/categoria/${slugCategoria(a.categoria)}`

  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org",
        "@graph": [
          {
            "@type": "BlogPosting",
            "@id": `${url}#articulo`,
            headline: a.titulo,
            alternativeHeadline: a.seoTitulo,
            description: a.descripcion,
            abstract: a.respuestaCorta,
            url,
            mainEntityOfPage: url,
            image: `${url}/opengraph-image`,
            datePublished: a.fecha,
            dateModified: a.fecha,
            inLanguage: "es-MX",
            articleSection: a.categoria,
            keywords: a.etiquetas.join(", "),
            wordCount: a.palabras,
            author: {
              "@type": "Person",
              "@id": `${SITE_URL}/blog/autor/${a.autor.slug}#persona`,
              name: a.autor.nombre,
              jobTitle: a.autor.cargo,
              url: `${SITE_URL}/blog/autor/${a.autor.slug}`,
              image: `${SITE_URL}${a.autor.foto}`,
              worksFor: { "@type": "Organization", name: a.autor.organizacion.nombre, url: a.autor.organizacion.url },
              sameAs: a.autor.sameAs,
            },
            publisher: { "@id": `${SITE_URL}/#org` },
            isPartOf: { "@id": `${SITE_URL}/blog#blog` },
            ...(a.fuente ? { isBasedOn: { "@type": "Book", name: a.fuente, author: { "@type": "Person", name: a.autor.nombre } } } : {}),
          },
          {
            "@type": "BreadcrumbList",
            itemListElement: [
              { "@type": "ListItem", position: 1, name: "Inicio", item: `${SITE_URL}/` },
              { "@type": "ListItem", position: 2, name: "Blog", item: `${SITE_URL}/blog` },
              { "@type": "ListItem", position: 3, name: a.categoria, item: `${SITE_URL}${urlCategoria}` },
              { "@type": "ListItem", position: 4, name: a.titulo, item: url },
            ],
          },
          ...(a.faq.length ? [{
            "@type": "FAQPage",
            "@id": `${url}#faq`,
            mainEntity: a.faq.map(f => ({
              "@type": "Question", name: f.pregunta,
              acceptedAnswer: { "@type": "Answer", text: f.respuesta },
            })),
          }] : []),
        ],
      }} />

      <article className="px-[var(--px-fluid)] pt-10 sm:pt-14">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto">
          {/* Ruta */}
          <nav aria-label="Ruta" className="text-[13px]" style={{ color: B.MUTED }}>
            <Link href="/blog" className="hover:text-[#152742]">Blog</Link>
            <span aria-hidden> / </span>
            <Link href={urlCategoria} className="hover:text-[#152742]">{a.categoria}</Link>
          </nav>

          {/* Encabezado */}
          <header className="mt-5 max-w-[46rem]">
            <Link href={urlCategoria} className="text-[11px] font-extrabold uppercase tracking-[0.12em] hover:underline" style={{ ...SANS, color: B.ACCENT }}>
              {a.categoria}
            </Link>
            <h1 className="mt-3" style={{ ...SANS, color: B.BNAVY, fontWeight: 700, fontSize: "clamp(30px, 4.2vw, 54px)", lineHeight: 1.08, letterSpacing: "-0.03em" }}>
              {a.titulo}
            </h1>
            <p className="mt-5 text-[17px] sm:text-[18px] leading-relaxed" style={{ color: B.INK2 }}>{a.descripcion}</p>
            <div className="mt-6 flex items-center gap-3">
              <Image src={a.autor.foto} alt={a.autor.nombre} width={44} height={44} className="h-11 w-11 rounded-full object-cover shrink-0" />
              <div className="text-[13.5px] leading-snug">
                <Link href={`/blog/autor/${a.autor.slug}`} className="font-semibold hover:underline" style={{ color: B.INK }}>{a.autor.nombre}</Link>
                <p style={{ color: B.MUTED }}>
                  {a.autor.cargo} · <time dateTime={a.fecha}>{fechaLarga(a.fecha)}</time> · {a.minutos} min de lectura
                </p>
              </div>
            </div>
          </header>

          <div className="mt-10 grid grid-cols-1 lg:grid-cols-[minmax(0,46rem)_1fr] gap-12">
            <div className="min-w-0">
              {/* Respuesta corta + puntos clave: lo primero que leen las personas y las IAs */}
              {(a.respuestaCorta || a.puntosClave.length > 0) && (
                <aside className="rounded-[26px] p-6 sm:p-7" style={{ background: B.CARD, border: `1px solid ${B.LINE}` }}>
                  {a.respuestaCorta && (
                    <>
                      <p className="text-[11px] font-extrabold uppercase tracking-[0.14em]" style={{ ...SANS, color: B.ACCENT }}>En resumen</p>
                      <p className="mt-2 text-[16px] leading-relaxed" style={{ color: B.INK }}>{a.respuestaCorta}</p>
                    </>
                  )}
                  {a.puntosClave.length > 0 && (
                    <>
                      <p className="mt-5 text-[11px] font-extrabold uppercase tracking-[0.14em]" style={{ ...SANS, color: B.MUTED }}>Puntos clave</p>
                      <ul className="mt-2 space-y-1.5 text-[15px] leading-relaxed" style={{ color: B.INK2 }}>
                        {a.puntosClave.map((p, i) => (
                          <li key={i} className="flex gap-2"><span aria-hidden style={{ color: B.ACCENT }}>—</span><span>{p}</span></li>
                        ))}
                      </ul>
                    </>
                  )}
                </aside>
              )}

              {/* Texto del autor */}
              <div className="articulo mt-10" dangerouslySetInnerHTML={{ __html: a.html }} />

              {/* Preguntas frecuentes */}
              {a.faq.length > 0 && (
                <section aria-labelledby="preguntas" className="mt-14">
                  <h2 id="preguntas" style={{ ...SANS, color: B.BNAVY, fontWeight: 700, fontSize: 26, letterSpacing: "-0.02em" }}>
                    Preguntas frecuentes
                  </h2>
                  <div className="mt-5" style={{ borderTop: `1px solid ${B.LINE}` }}>
                    {a.faq.map((f, i) => (
                      <details key={i} className="group py-4" style={{ borderBottom: `1px solid ${B.LINE}` }}>
                        <summary className="flex justify-between gap-4 text-[16px] font-semibold list-none" style={{ ...SANS, color: B.INK }}>
                          {f.pregunta}
                          <span aria-hidden className="shrink-0 transition-transform group-open:rotate-45" style={{ color: B.ACCENT }}>+</span>
                        </summary>
                        <p className="mt-3 text-[15px] leading-relaxed" style={{ color: B.INK2 }}>{f.respuesta}</p>
                      </details>
                    ))}
                  </div>
                </section>
              )}

              {/* Autor */}
              <section className="mt-14 rounded-[26px] p-6 sm:p-7 flex flex-col sm:flex-row gap-5" style={{ background: B.SAND }}>
                <Image src={a.autor.foto} alt={a.autor.nombre} width={80} height={80} className="h-20 w-20 self-start rounded-full object-cover shrink-0" />
                <div>
                  <p className="text-[11px] font-extrabold uppercase tracking-[0.14em]" style={{ ...SANS, color: B.MUTED }}>Sobre el autor</p>
                  <p className="mt-1 text-[18px] font-bold" style={{ ...SANS, color: B.INK }}>
                    <Link href={`/blog/autor/${a.autor.slug}`} className="hover:underline">{a.autor.nombre}</Link>
                  </p>
                  <p className="mt-2 text-[14.5px] leading-relaxed" style={{ color: B.INK2 }}>{a.autor.bio}</p>
                  {a.fuente && (
                    <p className="mt-3 text-[13px]" style={{ color: B.MUTED }}>Publicado originalmente en: {a.fuente}.</p>
                  )}
                </div>
              </section>
            </div>

            {/* Lateral: índice + invitación (solo escritorio) */}
            <aside className="hidden lg:block">
              <div className="sticky top-24 space-y-6">
                {a.indice.filter(h => h.nivel === 2).length > 1 && (
                  <nav aria-label="En este artículo" className="rounded-[26px] p-6" style={{ background: B.CARD, border: `1px solid ${B.LINE}` }}>
                    <p className="text-[11px] font-extrabold uppercase tracking-[0.14em]" style={{ ...SANS, color: B.MUTED }}>En este artículo</p>
                    <ol className="mt-3 space-y-2 text-[14px] leading-snug" style={{ color: B.INK2 }}>
                      {a.indice.filter(h => h.nivel === 2).map(h => (
                        <li key={h.id}><a href={`#${h.id}`} className="hover:text-[#152742]">{h.texto}</a></li>
                      ))}
                    </ol>
                  </nav>
                )}
                <CtaGobernia />
              </div>
            </aside>
          </div>

          <div className="lg:hidden mt-12"><CtaGobernia /></div>

          {rel.length > 0 && (
            <section aria-labelledby="relacionados" className="mt-16">
              <h2 id="relacionados" style={{ ...SANS, color: B.BNAVY, fontWeight: 700, fontSize: 26, letterSpacing: "-0.02em" }}>
                Sigue leyendo
              </h2>
              <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-5">
                {rel.map(r => <TarjetaArticulo key={r.slug} a={r} />)}
              </div>
            </section>
          )}
        </div>
      </article>
    </>
  )
}

function CtaGobernia() {
  return (
    <div className="rounded-[26px] p-6" style={{ background: B.BNAVY }}>
      <p className="text-[18px] font-bold leading-snug text-white" style={SANS}>
        Lleva estas prácticas a tu propio Consejo
      </p>
      <p className="mt-2 text-[14px] leading-relaxed" style={{ color: "rgba(255,255,255,.75)" }}>
        Gobernia es tu Consejo de Administración con IA: cinco consejeros analizan tu empresa y dan seguimiento a cada acuerdo.
      </p>
      <Link href="/sign-up"
        className="mt-5 inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-[13px] font-bold"
        style={{ ...SANS, background: "#FFFFFF", color: B.BNAVY }}>
        Comenzar gratis <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </div>
  )
}
