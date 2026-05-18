import { ReactNode } from "react"

export const dynamic = "force-dynamic"

export default function OnboardingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-white flex flex-col font-sans antialiased">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-black flex items-center justify-center">
            <span className="text-white text-[11px] font-black tracking-tight">G</span>
          </div>
          <span className="text-sm font-semibold text-black tracking-tight">Gobernia</span>
        </div>
        <span className="text-xs text-gray-400 tracking-wide">Configuración inicial</span>
      </header>

      {/* Content */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-10">
        {children}
      </main>

      {/* Footer */}
      <footer className="text-center py-4 text-xs text-gray-400">
        Tu información está protegida y cifrada.
      </footer>
    </div>
  )
}
