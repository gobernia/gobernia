import type { Metadata } from "next"
import { Inter, Newsreader } from "next/font/google"
import AuthSync from "@/components/AuthSync"
import CookieBanner from "@/components/CookieBanner"
import "./globals.css"

// Sistema de 2 roles: Inter para interfaz y cuerpo (máxima legibilidad, incluso en
// datos densos), Newsreader (serif) para los títulos (gravedad institucional).
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" })
const newsreader = Newsreader({ subsets: ["latin"], variable: "--font-news", display: "swap" })

export const metadata: Metadata = {
  title: "GOBERNIA — La evolución del Consejo de Administración",
  description:
    "Cinco consejeros con IA sesionan sobre tu empresa cada mes: detectan riesgos y proponen decisiones accionables. Las mejores prácticas corporativas, por una fracción del costo — sin contratar consultores.",
  keywords: [
    "consejo de administración con IA",
    "consejeros con IA para empresas",
    "junta directiva virtual",
    "consejeros corporativos",
    "CFO IA",
    "análisis estratégico mensual",
    "Gobernia",
  ],
  openGraph: {
    title: "GOBERNIA — La evolución del Consejo de Administración",
    description:
      "Cinco consejeros con IA analizan tu empresa cada mes, detectan riesgos y proponen decisiones. Sin consultores, sin esperas.",
    type: "website",
    locale: "es_MX",
    siteName: "GOBERNIA",
  },
  twitter: {
    card: "summary_large_image",
    title: "GOBERNIA — Tu Consejo de administración con IA",
    description:
      "Cinco consejeros con IA sesionan sobre tu empresa cada mes.",
  },
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="es"
      className={`h-full antialiased ${inter.variable} ${newsreader.variable}`}
    >
      <body className="min-h-full flex flex-col" style={{ fontFamily: "var(--font-sans)" }}>
        <AuthSync />
        {children}
        <CookieBanner />
      </body>
    </html>
  )
}
