import type { Metadata } from "next"

// La página de acceso no aporta en buscadores: no se indexa.
export const metadata: Metadata = {
  title: "Iniciar sesión — Gobernia",
  robots: { index: false, follow: true },
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
