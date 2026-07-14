"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import AgendaPanel from "@/components/plan/AgendaPanel"
import MinutaView from "@/components/plan/MinutaView"
import AlertsPanel from "@/components/plan/AlertsPanel"
import { PageShell } from "@/components/ui/PageShell"
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
    <main className="min-h-dvh bg-[var(--gob-bone)] py-10">
      <PageShell className="space-y-6">
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

        {/* Agenda y minuta son la sesión; las alertas la acompañan al costado. */}
        {hasPlan === true && (
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 items-start">
            <div className="xl:col-span-2 space-y-5">
              <AgendaPanel />
              <MinutaView />
            </div>
            <div className="space-y-5">
              <AlertsPanel />
            </div>
          </div>
        )}
      </PageShell>
    </main>
  )
}
