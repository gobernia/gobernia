"use client"

import CompromisosBoard from "@/components/plan/CompromisosBoard"

export default function CompromisosPage() {
  return (
    <main className="min-h-screen bg-[var(--gob-bone)] px-4 py-8">
      <div className="max-w-3xl mx-auto space-y-5">
        <div>
          <h1 className="text-3xl font-bold text-black tracking-tight">Compromisos</h1>
          <p className="text-sm text-gray-500 mt-1">
            Acuerdos del consejo con responsable y seguimiento. Copia el link para que el
            responsable reporte avance sin necesidad de cuenta.
          </p>
        </div>
        <CompromisosBoard />
      </div>
    </main>
  )
}
