import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Crea tu cuenta — Gobernia, Consejo de Administración con IA",
  description: "Crea tu cuenta en Gobernia y conoce a Todd, tu Secretario del Consejo: en menos de 30 minutos tienes el primer diagnóstico de tu empresa.",
  alternates: { canonical: "/sign-up" },
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
