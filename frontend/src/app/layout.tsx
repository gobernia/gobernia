import type { Metadata } from "next"
import { Space_Grotesk, Playfair_Display } from "next/font/google"
import AuthSync from "@/components/AuthSync"
import "./globals.css"

const font = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["300", "400", "500", "600", "700"],
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
  title: "Gobernia",
  description: "Gobierno corporativo inteligente",
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es" className={`${font.variable} ${display.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <AuthSync />
        {children}
      </body>
    </html>
  )
}
