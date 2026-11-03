import type { Metadata } from "next"

// Se llega aquí desde el enlace de recuperación, ya con sesión: no se indexa.
export const metadata: Metadata = {
  title: "Nueva contraseña — Gobernia",
  robots: { index: false, follow: false },
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
