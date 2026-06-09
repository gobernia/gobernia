"use client"

import { useEffect, useRef, useState } from "react"
import { Paperclip, Upload, X } from "lucide-react"
import { Evidence, getEvidence, uploadEvidence, deleteEvidence } from "@/lib/evidence"

export default function EvidenceSection({
  taskId, onCountChange,
}: { taskId: string; onCountChange?: (n: number) => void }) {
  const [items, setItems] = useState<Evidence[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const apply = (list: Evidence[]) => { setItems(list); onCountChange?.(list.length) }

  useEffect(() => {
    getEvidence(taskId).then(apply).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId])

  const onPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setBusy(true); setError(null)
    try {
      const ev = await uploadEvidence(taskId, file)
      apply([...items, ev])
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? "No se pudo subir la evidencia.")
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ""
    }
  }

  const onRemove = async (id: string) => {
    apply(items.filter(i => i.id !== id))
    await deleteEvidence(id).catch(() => getEvidence(taskId).then(apply))
  }

  return (
    <div className="space-y-1.5">
      <label className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">Evidencia</label>
      <div className="space-y-1.5">
        {items.map(e => (
          <div key={e.id} className="flex items-center gap-2 text-sm text-black bg-gray-50 rounded-lg px-3 py-2">
            <Paperclip className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
            <span className="flex-1 truncate">{e.filename}</span>
            <button type="button" onClick={() => onRemove(e.id)} className="text-gray-300 hover:text-red-500">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
        {items.length === 0 && (
          <p className="text-xs text-gray-400">Sin evidencia. Súbela para poder validar el acuerdo.</p>
        )}
      </div>
      <input ref={inputRef} type="file" className="hidden" onChange={onPick}
        accept=".pdf,.docx,.xlsx,.xls,.png,.jpg,.jpeg" />
      <button type="button" disabled={busy} onClick={() => inputRef.current?.click()}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--gob-navy)] hover:underline disabled:opacity-50">
        <Upload className="h-3.5 w-3.5" /> {busy ? "Subiendo…" : "Subir evidencia"}
      </button>
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  )
}
