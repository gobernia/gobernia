import type { Metadata } from "next"

// Página de recuperación de contraseña: no aporta en buscadores, no se indexa.
export const metadata: Metadata = {
  title: "Recuperar contraseña — Gobernia",
  robots: { index: false, follow: false },
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
