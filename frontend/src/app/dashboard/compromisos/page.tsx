"use client"

import CompromisosBoard from "@/components/plan/CompromisosBoard"
import { PageShell, Prose } from "@/components/ui/PageShell"

export default function CompromisosPage() {
  return (
    <main className="min-h-dvh bg-[var(--gob-bone)] py-10">
      <PageShell className="space-y-6">
        <div>
          <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Seguimiento</p>
          <h1 className="text-3xl font-bold text-black tracking-tight">Compromisos</h1>
          <Prose>
            <p className="text-sm text-gray-500 mt-1.5 leading-relaxed">
              Acuerdos del consejo con responsable y seguimiento. Copia el link para que el
              responsable reporte avance sin necesidad de cuenta.
            </p>
          </Prose>
        </div>
        <CompromisosBoard />
      </PageShell>
    </main>
  )
}
