import type { Metadata } from "next"
import { Inter, Newsreader } from "next/font/google"
import AuthSync from "@/components/AuthSync"
import CookieBanner from "@/components/CookieBanner"
import "./globals.css"
import { SITE_DESCRIPTION, SITE_NAME, SITE_TITLE, SITE_URL } from "@/lib/seo"

// Sistema de 2 roles: Inter para interfaz y cuerpo (máxima legibilidad, incluso en
// datos densos), Newsreader (serif) para los títulos (gravedad institucional).
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" })
const newsreader = Newsreader({ subsets: ["latin"], variable: "--font-news", display: "swap" })

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: SITE_TITLE,
  description: SITE_DESCRIPTION,
  applicationName: SITE_NAME,
  openGraph: {
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    type: "website",
    locale: "es_MX",
    siteName: SITE_NAME,
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
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
