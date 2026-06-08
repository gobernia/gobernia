"use client"

import { useEffect, useState } from "react"
import {
  BoardTheme, FREQ_LABEL, getThemes, updateTheme, createTheme, deleteTheme,
} from "@/lib/boardThemes"
import InfoHint from "@/components/ui/InfoHint"

const FREQ_OPTIONS = [1, 2, 3, 6, 12]
const TYPE_TITLES: Record<string, string> = {
  permanente: "Permanentes — cada sesión",
  cobertura: "Cobertura — rotan por frecuencia",
  emergente: "Emergentes — los inyecta el Secretario",
}

export default function ThemesPanel() {
  const [themes, setThemes] = useState<BoardTheme[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getThemes().then(setThemes).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const patch = async (id: string, p: Partial<BoardTheme>) => {
    setThemes(ts => ts.map(t => (t.id === id ? { ...t, ...p } : t)))
    await updateTheme(id, p).catch(() => getThemes().then(setThemes))
  }

  const remove = async (id: string) => {
    setThemes(ts => ts.filter(t => t.id !== id))
    await deleteTheme(id).catch(() => getThemes().then(setThemes))
  }

  const addCustom = async () => {
    const label = window.prompt("Nombre del tema")
    if (!label) return
    const created = await createTheme({ label, type: "cobertura", every_n_sessions: 3 })
    setThemes(ts => [...ts, created])
  }

  if (loading) return <p className="text-sm text-gray-400">Cargando temas…</p>

  const byType = (t: string) => themes.filter(x => x.type === t)

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-black flex items-center gap-2">
          Temas del Consejo
          <InfoHint text="Las responsabilidades que el Consejo debe cubrir en el año. La frecuencia indica cada cuántas sesiones se revisa cada tema." />
        </h2>
        <button onClick={addCustom} className="text-xs font-medium text-[var(--gob-navy)] hover:underline">
          + Agregar tema
        </button>
      </div>

      {["permanente", "cobertura", "emergente"].map(type => {
        const list = byType(type)
        if (type === "emergente" && list.length === 0) return null
        return (
          <div key={type} className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-400">{TYPE_TITLES[type]}</p>
            <div className="space-y-2">
              {list.map(t => (
                <div key={t.id} className={`flex items-center gap-3 rounded-xl border border-gray-100 px-4 py-3 ${t.active ? "" : "opacity-50"}`}>
                  <span className="flex-1 text-sm text-black">{t.label}</span>
                  {t.type === "cobertura" && (
                    <select
                      value={t.every_n_sessions ?? 3}
                      onChange={e => patch(t.id, { every_n_sessions: Number(e.target.value) })}
                      className="text-xs border border-gray-200 rounded-lg px-2 py-1 text-gray-700"
                    >
                      {FREQ_OPTIONS.map(f => <option key={f} value={f}>{FREQ_LABEL[f]}</option>)}
                    </select>
                  )}
                  {t.type === "permanente" && (
                    <span className="text-xs text-gray-400">cada sesión</span>
                  )}
                  <button
                    onClick={() => patch(t.id, { active: !t.active })}
                    className="text-xs text-gray-500 hover:text-[var(--gob-navy)]"
                  >
                    {t.active ? "Desactivar" : "Activar"}
                  </button>
                  {!t.is_default && (
                    <button onClick={() => remove(t.id)} className="text-xs text-red-400 hover:text-red-600">
                      Borrar
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
