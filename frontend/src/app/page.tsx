import type { Metadata } from "next"
import LandingHome from "@/components/landing/LandingHome"
import { FAQS } from "@/components/landing/faqs"
import { SAME_AS, SITE_DEFINICION, SITE_DESCRIPTION, SITE_NAME, SITE_TITLE, SITE_URL } from "@/lib/seo"

export const metadata: Metadata = {
  alternates: { canonical: "/" },
  openGraph: {
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    url: "/",
    type: "website",
    locale: "es_MX",
    siteName: SITE_NAME,
  },
}

// Datos estructurados: que Google y las IAs reconozcan a Gobernia como organización y
// software, y lean las preguntas frecuentes tal como están en la página.
const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": `${SITE_URL}/#org`,
      name: SITE_NAME,
      alternateName: "Gobernia — Consejo de Administración con IA",
      url: `${SITE_URL}/`,
      logo: `${SITE_URL}/icon.svg`,
      description: SITE_DEFINICION,
      disambiguatingDescription:
        "Software de gobierno corporativo con IA para empresas; no relacionado con plataformas de gestión gubernamental de nombre similar.",
      areaServed: ["MX", "Latinoamérica"],
      ...(SAME_AS.length ? { sameAs: SAME_AS } : {}),
    },
    {
      "@type": "WebSite",
      "@id": `${SITE_URL}/#website`,
      url: `${SITE_URL}/`,
      name: SITE_NAME,
      inLanguage: "es-MX",
      publisher: { "@id": `${SITE_URL}/#org` },
    },
    {
      "@type": "SoftwareApplication",
      "@id": `${SITE_URL}/#software`,
      name: SITE_NAME,
      url: `${SITE_URL}/`,
      description: SITE_DEFINICION,
      applicationCategory: "BusinessApplication",
      operatingSystem: "Web",
      inLanguage: "es-MX",
      publisher: { "@id": `${SITE_URL}/#org` },
      audience: { "@type": "BusinessAudience", audienceType: "Empresas familiares y PyMEs" },
      featureList: [
        "Cinco consejeros con IA: Finanzas, Estrategia, Riesgos, Auditoría e Independiente",
        "Secretario del Consejo con IA (Todd)",
        "Diagnóstico FODA y estrategia a 3 años",
        "Orden del día y sesiones del Consejo por periodo (mensual, trimestral o semestral)",
        "Acuerdos con responsable y fecha, y seguimiento con evidencia",
      ],
    },
    {
      "@type": "FAQPage",
      "@id": `${SITE_URL}/#faq`,
      mainEntity: FAQS.map(f => ({
        "@type": "Question",
        name: f.q,
        acceptedAnswer: { "@type": "Answer", text: f.a },
      })),
    },
  ],
}

export default function Home() {
  return (
    <>
      <script
        type="application/ld+json"
        // JSON de contenido propio (sin datos del usuario): seguro de incrustar.
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }}
      />
      <LandingHome />
    </>
  )
}
