"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import AgendaPanel from "@/components/plan/AgendaPanel"
import MinutaView from "@/components/plan/MinutaView"
import AlertsPanel from "@/components/plan/AlertsPanel"
import { MONTH_NAMES, getAnnualPlanStatus } from "@/lib/annualPlan"

export default function SesionDelMesPage() {
  const [hasPlan, setHasPlan] = useState<boolean | null>(null)

  useEffect(() => {
    let active = true
    getAnnualPlanStatus()
      .then(() => { if (active) setHasPlan(true) })
      .catch(() => { if (active) setHasPlan(false) })
    return () => { active = false }
  }, [])

  const now = new Date()

  return (
    <main className="min-h-screen bg-[var(--gob-bone)] px-4 py-8">
      <div className="max-w-3xl mx-auto space-y-5">
        <div>
          <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Tu sesión de</p>
          <h1 className="text-3xl font-bold text-black tracking-tight">
            {MONTH_NAMES[now.getMonth() + 1]} {now.getFullYear()}
          </h1>
        </div>

        {hasPlan === null && <p className="text-sm text-gray-400">Cargando…</p>}

        {hasPlan === false && (
          <div className="rounded-2xl border border-gray-100 bg-white p-6 text-center">
            <p className="text-sm text-gray-500 mb-3">
              Aún no tienes un plan estratégico. Genera tu plan para convocar a tu consejo.
            </p>
            <Link
              href="/dashboard/plan"
              className="inline-block px-4 py-2 rounded-lg bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium"
            >
              Ir al Plan
            </Link>
          </div>
        )}

        {hasPlan === true && (
          <>
            <AgendaPanel />
            <MinutaView />
            <AlertsPanel />
          </>
        )}
      </div>
    </main>
  )
}
