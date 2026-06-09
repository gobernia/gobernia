"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { X, Trash2, User, Calendar, Tag, Target } from "lucide-react"
import type { Task, TaskStatus, TaskPriority } from "@/lib/annualPlan"
import InfoHint from "@/components/ui/InfoHint"
import EvidenceSection from "@/components/plan/EvidenceSection"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

const STATUSES: { id: TaskStatus; label: string }[] = [
  { id: "pendiente", label: "Pendiente" },
  { id: "en_progreso", label: "En proceso" },
  { id: "completada", label: "Validado" },
]

const PRIORITIES: { id: TaskPriority; label: string }[] = [
  { id: "alta", label: "Alta" },
  { id: "media", label: "Media" },
  { id: "baja", label: "Baja" },
]

export default function TaskDrawer({
  task, kpiOptions, onClose, onUpdate, onDelete,
}: {
  task: Task
  kpiOptions: string[]
  onClose: () => void
  onUpdate: (patch: Partial<Task>) => void
  onDelete: () => void
}) {
  const [local, setLocal] = useState<Task>(task)
  const [evidenceCount, setEvidenceCount] = useState(0)
  const [statusError, setStatusError] = useState<string | null>(null)
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setLocal(task), [task])

  const save = (patch: Partial<Task>) => {
    setLocal(prev => ({ ...prev, ...patch }))
    onUpdate(patch)
  }

  const onStatusClick = (s: string) => {
    if (s === "completada" && evidenceCount === 0) {
      setStatusError("Sube una evidencia para validar este acuerdo.")
      return
    }
    setStatusError(null)
    save({ status: s as TaskStatus })
  }

  return (
    <>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
      />
      <motion.div
        initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 40 }}
        transition={{ duration: 0.3, ease: EASE }}
        className="fixed z-50 inset-y-0 right-0 w-full sm:w-[460px] bg-white shadow-2xl overflow-y-auto"
      >
        <div className="sticky top-0 z-10 bg-white border-b border-gray-100 px-6 h-14 flex items-center justify-between">
          <span className="text-xs font-medium text-gray-400 uppercase tracking-widest">Tarea</span>
          <button onClick={onClose} className="text-gray-400 hover:text-[var(--gob-navy)] transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          <textarea
            value={local.title}
            onChange={e => setLocal(p => ({ ...p, title: e.target.value }))}
            onBlur={() => local.title !== task.title && save({ title: local.title })}
            rows={2}
            className="w-full text-lg font-bold text-black resize-none focus:outline-none placeholder:text-gray-300"
            placeholder="Título de la tarea"
          />

          <div className="space-y-1.5">
            <label className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">Estado</label>
            <div className="flex gap-1.5">
              {STATUSES.map(s => (
                <button
                  key={s.id}
                  onClick={() => onStatusClick(s.id)}
                  className={`flex-1 text-xs font-medium py-2 rounded-lg border-2 transition-all ${
                    local.status === s.id
                      ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                      : "border-gray-100 text-gray-500 hover:border-gray-300"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
            {statusError && <p className="text-xs text-red-500">{statusError}</p>}
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">Prioridad <InfoHint text="Qué tan importante o urgente es la tarea: alta, media o baja." /></label>
            <div className="flex gap-1.5">
              {PRIORITIES.map(p => (
                <button
                  key={p.id}
                  onClick={() => save({ priority: p.id })}
                  className={`flex-1 text-xs font-medium py-2 rounded-lg border-2 transition-all ${
                    local.priority === p.id
                      ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                      : "border-gray-100 text-gray-500 hover:border-gray-300"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">Descripción</label>
            <textarea
              value={local.description ?? ""}
              onChange={e => setLocal(p => ({ ...p, description: e.target.value }))}
              onBlur={() => local.description !== task.description && save({ description: local.description })}
              rows={4}
              placeholder="Detalles, contexto, criterios de éxito…"
              className="w-full text-sm text-black bg-gray-50 rounded-xl px-3 py-2.5 focus:outline-none focus:bg-white focus:ring-1 focus:ring-[var(--gob-navy)] resize-none"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-medium tracking-widest text-gray-400 uppercase flex items-center gap-1.5">
              <User className="h-3 w-3" /> Responsable
            </label>
            <input
              value={local.owner ?? ""}
              onChange={e => setLocal(p => ({ ...p, owner: e.target.value }))}
              onBlur={() => local.owner !== task.owner && save({ owner: local.owner || null })}
              placeholder="Director General, CFO, Consejo…"
              className="w-full text-sm text-black bg-gray-50 rounded-xl px-3 py-2.5 focus:outline-none focus:bg-white focus:ring-1 focus:ring-[var(--gob-navy)]"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-medium tracking-widest text-gray-400 uppercase flex items-center gap-1.5">
              <Calendar className="h-3 w-3" /> Fecha límite
            </label>
            <input
              type="date"
              value={local.due_date ?? ""}
              onChange={e => save({ due_date: e.target.value || null })}
              className="w-full text-sm text-black bg-gray-50 rounded-xl px-3 py-2.5 focus:outline-none focus:bg-white focus:ring-1 focus:ring-[var(--gob-navy)]"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-medium tracking-widest text-gray-400 uppercase flex items-center gap-1.5">
              <Target className="h-3 w-3" /> Impacto KPI <InfoHint text="El indicador clave (KPI) al que ayuda esta tarea cuando se completa." />
            </label>
            <select
              value={local.kpi_ref ?? ""}
              onChange={e => save({ kpi_ref: e.target.value || null })}
              className="w-full text-sm text-black bg-gray-50 rounded-xl px-3 py-2.5 focus:outline-none focus:bg-white focus:ring-1 focus:ring-[var(--gob-navy)]"
            >
              <option value="">Sin KPI</option>
              {kpiOptions.map(k => <option key={k} value={k}>{k}</option>)}
              {local.kpi_ref && !kpiOptions.includes(local.kpi_ref) && (
                <option value={local.kpi_ref}>{local.kpi_ref}</option>
              )}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-medium tracking-widest text-gray-400 uppercase flex items-center gap-1.5">
              <Tag className="h-3 w-3" /> Etiquetas
            </label>
            <input
              value={local.tags.join(", ")}
              onChange={e => setLocal(p => ({ ...p, tags: e.target.value.split(",").map(s => s.trim()).filter(Boolean) }))}
              onBlur={() => save({ tags: local.tags })}
              placeholder="compliance, liquidez, talento"
              className="w-full text-sm text-black bg-gray-50 rounded-xl px-3 py-2.5 focus:outline-none focus:bg-white focus:ring-1 focus:ring-[var(--gob-navy)]"
            />
          </div>

          <EvidenceSection taskId={task.id} onCountChange={setEvidenceCount} />

          <button
            onClick={onDelete}
            className="w-full flex items-center justify-center gap-2 text-xs font-medium text-red-500 hover:text-red-700 border border-red-100 hover:border-red-300 rounded-xl py-2.5 transition-colors"
          >
            <Trash2 className="h-3.5 w-3.5" /> Borrar tarea
          </button>
        </div>
      </motion.div>
    </>
  )
}
