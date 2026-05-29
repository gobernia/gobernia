"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ChevronDown, Sparkles } from "lucide-react"

function renderLine(line: string, i: number) {
  const m = line.match(/^\*\*(.+?):\*\*\s*(.*)$/)
  if (m) {
    return (
      <p key={i} className="text-sm text-gray-600 leading-relaxed">
        <span className="font-bold text-black">{m[1]}:</span> {m[2]}
      </p>
    )
  }
  return <p key={i} className="text-sm text-gray-600 leading-relaxed">{line}</p>
}

export default function DiagnosticoPanel({ summary }: { summary: string | null }) {
  const [open, setOpen] = useState(true)
  if (!summary) return null

  const lines = summary.split("\n").filter(l => l.trim().length > 0)

  return (
    <div className="border border-gray-100 rounded-2xl overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <Sparkles className="h-4 w-4 text-[var(--gob-navy)]" />
          <span className="text-sm font-bold text-black">Diagnóstico del consejo</span>
        </div>
        <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown className="h-4 w-4 text-gray-400" />
        </motion.div>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 space-y-2.5 border-t border-gray-50 pt-4">
              {lines.map(renderLine)}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
