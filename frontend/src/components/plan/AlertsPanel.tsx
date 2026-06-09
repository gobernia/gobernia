"use client"

import { useEffect, useState } from "react"
import { AlertItem, AlertLevel, getAlertas } from "@/lib/alerts"

const BORDER: Record<AlertLevel, string> = {
  critical: "border-red-400 bg-red-50/50",
  warning: "border-amber-400 bg-amber-50/50",
  info: "border-gray-300 bg-gray-50",
}

export default function AlertsPanel() {
  const [alerts, setAlerts] = useState<AlertItem[]>([])

  useEffect(() => {
    let active = true
    getAlertas().then(a => { if (active) setAlerts(a) }).catch(() => {})
    return () => { active = false }
  }, [])

  if (alerts.length === 0) return null

  return (
    <div className="space-y-2 mb-4">
      {alerts.map((a, i) => (
        <div
          key={i}
          className={`text-sm text-gray-700 border-l-4 rounded-r-lg px-3 py-2 ${BORDER[a.level] ?? BORDER.info}`}
        >
          {a.message}
        </div>
      ))}
    </div>
  )
}
