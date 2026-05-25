import type { Metadata } from "next"
import AuthSync from "@/components/AuthSync"
import CookieBanner from "@/components/CookieBanner"
import "./globals.css"

// Gabriel Sans se carga vía @font-face en globals.css (self-hosted).
// Una sola familia para todo el sistema — la jerarquía se construye con pesos.

export const metadata: Metadata = {
  title: "GOBERNIA — Sesión de consejo cada mes, con cuatro agentes de IA",
  description:
    "Tu consejo de administración impulsado por IA. CFO, CSO, CRO y Auditor revisan tu empresa, detectan riesgos y proponen decisiones cada mes. Sin contratar consultores.",
  keywords: [
    "consejo de administración con IA",
    "agentes de IA para empresas",
    "junta directiva virtual",
    "consejeros corporativos",
    "CFO IA",
    "análisis estratégico mensual",
    "Gobernia",
  ],
  openGraph: {
    title: "GOBERNIA — Sesión de consejo cada mes, con cuatro agentes de IA",
    description:
      "CFO, CSO, CRO y Auditor de IA analizan tu empresa cada mes, detectan riesgos y proponen decisiones. Sin consultores, sin esperas.",
    type: "website",
    locale: "es_MX",
    siteName: "GOBERNIA",
  },
  twitter: {
    card: "summary_large_image",
    title: "GOBERNIA — Tu consejo de administración con IA",
    description:
      "Cuatro agentes de IA — CFO, CSO, CRO y Auditor — revisan tu empresa cada mes.",
  },
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="es"
      className="h-full antialiased"
      style={{ ["--font-sans" as string]: '"Gabriel Sans", system-ui, sans-serif' }}
    >
      <body className="min-h-full flex flex-col" style={{ fontFamily: "var(--font-sans)" }}>
        <AuthSync />
        {children}
        <CookieBanner />
      </body>
    </html>
  )
}
