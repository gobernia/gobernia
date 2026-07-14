"use client"

import { Check, Loader2, Pencil } from "lucide-react"

/** Editar / Guardar / Cancelar de cada bloque. Con `hide` (roadmap validado) no se pinta nada. */
export default function EditControls({ editing, onEdit, onSave, onCancel, saving, hide = false }: {
  editing: boolean; onEdit: () => void; onSave: () => void; onCancel: () => void; saving: boolean
  hide?: boolean
}) {
  if (hide) return null
  return editing ? (
    <div className="flex items-center gap-2 shrink-0">
      <button onClick={onSave} disabled={saving}
        className="inline-flex items-center gap-1.5 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-medium px-3 py-1.5 rounded-lg hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
        {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />} Guardar
      </button>
      <button onClick={onCancel} disabled={saving}
        className="text-xs font-medium text-[var(--gob-muted)] hover:text-[var(--gob-ink)] px-2 rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
        Cancelar
      </button>
    </div>
  ) : (
    <button onClick={onEdit}
      className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--gob-stone)] hover:text-[var(--gob-navy)] transition-colors shrink-0 rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
      <Pencil className="h-3.5 w-3.5" /> Editar
    </button>
  )
}
