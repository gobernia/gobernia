"use client"

import { useEffect, useState } from "react"
import { CoverageRow, CoverageEstado, getCobertura } from "@/lib/coverage"

const ESTADO: Record<CoverageEstado, { label: string; cls: string }> = {
  en_tiempo: { label: "En tiempo", cls: "bg-green-100 text-green-700" },
  riesgo:    { label: "Riesgo",    cls: "bg-amber-100 text-amber-700" },
  atrasado:  { label: "Atrasado",  cls: "bg-orange-100 text-orange-700" },
  critico:   { label: "Crítico",   cls: "bg-red-100 text-red-700" },
}

export default function CoberturaBoard() {
  const [rows, setRows] = useState<CoverageRow[] | null>(null)

  useEffect(() => {
    let active = true
    getCobertura().then(r => { if (active) setRows(r) }).catch(() => { if (active) setRows([]) })
    return () => { active = false }
  }, [])

  if (rows === null) return <p className="text-sm text-gray-400">Cargando cobertura…</p>
  if (rows.length === 0) return <p className="text-sm text-gray-400">Sin temas de cobertura.</p>

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-gray-400 border-b border-gray-100">
            <th className="py-2 pr-4 font-medium">Tema</th>
            <th className="py-2 px-3 font-medium text-center">Frecuencia</th>
            <th className="py-2 px-3 font-medium text-center">Esperadas</th>
            <th className="py-2 px-3 font-medium text-center">Realizadas</th>
            <th className="py-2 pl-3 font-medium">Estado</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const e = ESTADO[r.estado]
            return (
              <tr key={r.key} className="border-b border-gray-50">
                <td className="py-2.5 pr-4 text-black">{r.label}</td>
                <td className="py-2.5 px-3 text-center text-gray-500">{r.frecuencia_anual}</td>
                <td className="py-2.5 px-3 text-center text-gray-500">{r.esperadas}</td>
                <td className="py-2.5 px-3 text-center text-gray-500">{r.realizadas}</td>
                <td className="py-2.5 pl-3">
                  <span className={`inline-block text-[11px] font-medium px-2 py-0.5 rounded-md ${e.cls}`}>{e.label}</span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
