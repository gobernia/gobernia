"use client"

import { useEffect, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { X } from "lucide-react"
import { getAlertas, type AlertItem } from "@/lib/alerts"

const BORDER: Record<string, string> = {
  critical: "border-red-400 bg-red-50",
  warning: "border-amber-400 bg-amber-50",
  info: "border-gray-300 bg-gray-50",
}
const KEY = "gobernia_notices_dismissed"

function getDismissed(): Set<string> {
  if (typeof window === "undefined") return new Set()
  try { return new Set(JSON.parse(sessionStorage.getItem(KEY) || "[]")) } catch { return new Set() }
}
function addDismissed(msg: string) {
  if (typeof window === "undefined") return
  const s = getDismissed(); s.add(msg)
  sessionStorage.setItem(KEY, JSON.stringify([...s]))
}

export default function Notices() {
  const [alerts, setAlerts] = useState<AlertItem[]>([])

  useEffect(() => {
    getAlertas()
      .then(a => {
        const dismissed = getDismissed()
        setAlerts(a.filter(x => !dismissed.has(x.message)))
      })
      .catch(() => {})
  }, [])

  const dismissOne = (msg: string) => {
    addDismissed(msg)
    setAlerts(prev => prev.filter(a => a.message !== msg))
  }

  if (alerts.length === 0) return null

  return (
    <div className="fixed top-4 right-4 z-50 w-80 max-w-[calc(100vw-2rem)] space-y-2">
      <AnimatePresence>
        {alerts.map(a => (
          <motion.div
            key={a.message}
            initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 30 }}
            transition={{ duration: 0.25 }}
            className={`relative rounded-xl border-l-4 shadow-sm px-4 py-3 pr-8 text-sm text-gray-700 ${BORDER[a.level] ?? BORDER.info}`}
          >
            {a.message}
            <button onClick={() => dismissOne(a.message)} aria-label="Cerrar"
              className="absolute top-2 right-2 text-gray-400 hover:text-gray-700">
              <X className="h-3.5 w-3.5" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
