import { ReactNode } from "react"
import GoberniaLogo from "@/components/ui/GoberniaLogo"

export const dynamic = "force-dynamic"

export default function OnboardingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-white flex flex-col font-sans antialiased">
      {/* Header */}
      <header className="flex items-center justify-between px-[var(--px-fluid)] py-4 border-b border-[var(--gob-rule)]/60">
        <GoberniaLogo size={16} />
        <span className="text-xs text-[var(--gob-stone)] tracking-wide hidden sm:inline">Configuración inicial</span>
      </header>

      {/* Content */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 sm:px-[var(--px-fluid)] py-8 sm:py-10">
        {children}
      </main>

      {/* Footer */}
      <footer className="text-center py-4 px-4 text-xs text-[var(--gob-stone)]">
        Tu información está protegida y cifrada.
      </footer>
    </div>
  )
}
