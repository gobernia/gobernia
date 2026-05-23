import type { Metadata } from "next"
import { Gabarito, Playfair_Display } from "next/font/google"
import AuthSync from "@/components/AuthSync"
import "./globals.css"

const sans = Gabarito({
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["400", "500", "600", "700", "800", "900"],
  display: "swap",
})

const display = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-display",
  style: ["italic"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
})

export const metadata: Metadata = {
  title: "GOBERNIA",
  description: "Tu junta de consejo, con inteligencia de agentes.",
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es" className={`${sans.variable} ${display.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <AuthSync />
        {children}
      </body>
    </html>
  )
}
