"use client"

import { useEffect, useRef, useState } from "react"
import { useParams } from "next/navigation"
import {
  Escritorio,
  ExplicacionTarea,
  TareaColab,
  explicarTarea,
  getEscritorio,
} from "@/lib/colaborador"

const NAVY = "#142849"
const BONE = "#f7f5ef"

type EstadoMeta = { label: string; bg: string; fg: string }
const ESTADOS: Record<string, EstadoMeta> = {
  pendiente: { label: "Pendiente", bg: "#e5e7eb", fg: "#374151" },
  en_progreso: { label: "En proceso", bg: "#fef3c7", fg: "#b45309" },
  completada: { label: "Hecho", bg: "#d1fae5", fg: "#0f766e" },
}

function estadoMeta(status: string): EstadoMeta {
  return ESTADOS[status] ?? { label: status, bg: "#e5e7eb", fg: "#374151" }
}

function fmtFecha(iso: string | null): string | null {
  if (!iso) return null
  try {
    return new Date(iso + "T00:00:00").toLocaleDateString("es-MX", {
      day: "numeric",
      month: "long",
      year: "numeric",
    })
  } catch {
    return iso
  }
}

function TarjetaTarea({ token, tarea }: { token: string; tarea: TareaColab }) {
  const [abierto, setAbierto] = useState(false)
  const [exp, setExp] = useState<ExplicacionTarea | null>(tarea.explicacion)
  const [cargando, setCargando] = useState(false)
  const aliveRef = useRef(true)
  useEffect(() => {
    aliveRef.current = true
    return () => {
      aliveRef.current = false
    }
  }, [])

  const meta = estadoMeta(tarea.status)
  const fecha = fmtFecha(tarea.due_date)

  const toggle = async () => {
    const siguiente = !abierto
    setAbierto(siguiente)
    if (siguiente && !exp && !cargando) {
      setCargando(true)
      try {
        const d = await explicarTarea(token, tarea.id)
        if (aliveRef.current) setExp(d)
      } catch {
        /* noop */
      } finally {
        if (aliveRef.current) setCargando(false)
      }
    }
  }

  return (
    <div className="rounded-2xl border border-black/5 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-base font-semibold" style={{ color: NAVY }}>
          {tarea.title}
        </h2>
        <span
          className="shrink-0 rounded-full px-2.5 py-1 text-xs font-medium"
          style={{ backgroundColor: meta.bg, color: meta.fg }}
        >
          {meta.label}
        </span>
      </div>

      {tarea.description && (
        <p className="mt-1.5 text-sm text-gray-600">{tarea.description}</p>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
        {fecha && <span>Para el {fecha}</span>}
        {tarea.objetivo && <span className="text-gray-400">Objetivo: {tarea.objetivo}</span>}
      </div>

      <button
        type="button"
        onClick={toggle}
        aria-expanded={abierto}
        className="mt-3 inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors"
        style={{ borderColor: "#dfe3ea", color: NAVY }}
      >
        {abierto ? "Ocultar" : "¿Qué es y cómo hacerla?"}
      </button>

      {abierto && (
        <div className="mt-3 rounded-xl border border-black/5 p-4" style={{ backgroundColor: BONE }}>
          {cargando && !exp ? (
            <p className="text-sm text-gray-500">Preparando la explicación de Todd…</p>
          ) : exp ? (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <span className="rounded-full bg-white px-2.5 py-1 text-xs text-gray-600 border border-black/5">
                  Tiempo: {exp.tiempo}
                </span>
                <span className="rounded-full bg-white px-2.5 py-1 text-xs text-gray-600 border border-black/5">
                  Dificultad: {exp.dificultad}
                </span>
              </div>
              {exp.que_es && <p className="text-sm text-gray-700">{exp.que_es}</p>}
              {exp.como.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
                    Cómo hacerla
                  </p>
                  <ol className="list-decimal space-y-1 pl-5 text-sm text-gray-700">
                    {exp.como.map((paso, i) => (
                      <li key={i}>{paso}</li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-500">No se pudo cargar la explicación. Intenta de nuevo.</p>
          )}
        </div>
      )}
    </div>
  )
}

export default function EscritorioPage() {
  const params = useParams<{ token: string }>()
  const token = params.token
  const [data, setData] = useState<Escritorio | null>(null)
  const [notFound, setNotFound] = useState(false)
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    getEscritorio(token)
      .then(d => {
        if (aliveRef.current) setData(d)
      })
      .catch(() => {
        if (aliveRef.current) setNotFound(true)
      })
    return () => {
      aliveRef.current = false
    }
  }, [token])

  if (notFound) {
    return (
      <main className="flex min-h-screen items-center justify-center p-6 text-gray-500" style={{ backgroundColor: BONE }}>
        Enlace no encontrado.
      </main>
    )
  }
  if (!data) {
    return (
      <main className="flex min-h-screen items-center justify-center p-6 text-gray-400" style={{ backgroundColor: BONE }}>
        Cargando…
      </main>
    )
  }

  return (
    <main className="min-h-screen p-6" style={{ backgroundColor: BONE }}>
      <div className="mx-auto w-full max-w-2xl space-y-5">
        <header className="pt-2">
          <p className="text-xs font-semibold uppercase tracking-[0.2em]" style={{ color: NAVY }}>
            Gobernia
          </p>
          <h1 className="mt-2 text-2xl font-bold" style={{ color: NAVY }}>
            Hola {data.nombre || "tu equipo"}
          </h1>
          <p className="mt-1 text-base text-gray-600">
            Tus tareas{data.empresa ? ` — ${data.empresa}` : ""}
          </p>
          <p className="mt-2 text-sm text-gray-500">
            Estas son las tareas que te asignaron. Toca una para ver de qué trata y cómo hacerla.
          </p>
        </header>

        {data.tareas.length === 0 ? (
          <div className="rounded-2xl border border-black/5 bg-white p-8 text-center text-sm text-gray-500">
            Aún no tienes tareas asignadas.
          </div>
        ) : (
          <div className="space-y-3">
            {data.tareas.map(t => (
              <TarjetaTarea key={t.id} token={token} tarea={t} />
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
