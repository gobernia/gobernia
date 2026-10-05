import type { Metadata } from "next"

// Landing anterior (respaldo): no debe competir con la home en buscadores.
export const metadata: Metadata = {
  robots: { index: false, follow: false },
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
