"use client"

import { useEffect, useRef, useState } from "react"
import { useParams } from "next/navigation"
import {
  Escritorio,
  ExplicacionTarea,
  TareaColab,
  ToddMensaje,
  ValidacionColab,
  enviarToddResponsable,
  explicarTarea,
  getEscritorio,
  getToddChat,
  subirEvidenciaColab,
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

// Lo que dijo el Auditor del documento subido, en palabras para el responsable.
const VEREDICTO: Record<string, { label: string; color: string }> = {
  validada: { label: "Validado por el Auditor", color: "#0f766e" },
  parcial: { label: "Avance parcial", color: "#1d4ed8" },
  insuficiente: { label: "Falta sustento", color: "#b45309" },
  sin_revisar: { label: "Sin revisar", color: "#6b7280" },
  revisando: { label: "El Auditor lo está leyendo…", color: NAVY },
}
const ACEPTA = ".pdf,.png,.jpg,.jpeg,.xlsx,.xls,.docx,.pptx"

function detalleDelError(err: unknown): string | null {
  const d = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof d === "string" ? d : null
}

function Evidencia({ token, tarea, onSubido }: {
  token: string
  tarea: TareaColab
  onSubido: () => void
}) {
  const [subiendo, setSubiendo] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const v: ValidacionColab | null | undefined = tarea.validacion
  const meta = v ? VEREDICTO[v.estado] : undefined
  const n = tarea.evidencias ?? 0

  const subir = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setSubiendo(true)
    setError(null)
    try {
      await subirEvidenciaColab(token, tarea.id, file)
      onSubido()
    } catch (err) {
      setError(detalleDelError(err) ?? "No se pudo subir el documento. Intenta de nuevo.")
    } finally {
      setSubiendo(false)
      if (inputRef.current) inputRef.current.value = ""
    }
  }

  return (
    <div className="mt-4 rounded-xl border border-black/5 p-4 space-y-2.5" style={{ backgroundColor: BONE }}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Evidencia{n > 0 ? ` · ${n} ${n === 1 ? "documento" : "documentos"}` : ""}
        </p>
        <button type="button" disabled={subiendo} onClick={() => inputRef.current?.click()}
          className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
          style={{ backgroundColor: NAVY }}>
          {subiendo ? "Subiendo…" : n > 0 ? "Subir otro documento" : "Subir documento"}
        </button>
        <input ref={inputRef} type="file" className="hidden" accept={ACEPTA} onChange={subir} />
      </div>
      {error && <p className="text-xs" style={{ color: "#b45309" }}>{error}</p>}
      {n === 0 && !v && (
        <p className="text-xs text-gray-500">
          Sube aquí el documento que demuestra que la tarea avanzó: PDF, imagen, Excel, Word o PowerPoint (hasta 10 MB).
          El Auditor lo revisa al momento y te dice si alcanza.
        </p>
      )}
      {v && meta && (
        <div className="space-y-1.5 text-sm text-gray-700">
          <p className="text-xs font-semibold" style={{ color: meta.color }}>{meta.label}</p>
          {v.estado !== "revisando" && (
            <>
              {v.otro_documento && (
                <p>Parece que se subió otro documento{v.documento ? <>: es <strong>{v.documento}</strong></> : ""}.</p>
              )}
              {!v.otro_documento && v.documento && <p className="text-xs text-gray-500">Es {v.documento}.</p>}
              {v.cubre && <p><strong>Ya está:</strong> {v.cubre}</p>}
              {v.estado !== "validada" && (v.falta || v.motivo) && (
                <p><strong>{v.otro_documento ? "Lo que se necesita:" : "Falta:"}</strong> {v.falta || v.motivo}</p>
              )}
              {v.estado === "validada" && !v.cubre && v.motivo && <p>{v.motivo}</p>}
              {v.alternativas && v.alternativas.length > 0 && (
                <div>
                  <p className="text-xs text-gray-500">Si no tienes ese documento, también sirve:</p>
                  <ul className="list-disc pl-5 text-sm">
                    {v.alternativas.map((a, i) => <li key={i}>{a}</li>)}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function TarjetaTarea({ token, tarea, onCambio }: { token: string; tarea: TareaColab; onCambio: () => void }) {
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

      <Evidencia token={token} tarea={tarea} onSubido={onCambio} />
    </div>
  )
}

function ToddChat({ token }: { token: string }) {
  const [abierto, setAbierto] = useState(false)
  const [mensajes, setMensajes] = useState<ToddMensaje[]>([])
  const [texto, setTexto] = useState("")
  const [enviando, setEnviando] = useState(false)
  const aliveRef = useRef(true)
  const cargadoRef = useRef(false)
  const finRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    aliveRef.current = true
    return () => {
      aliveRef.current = false
    }
  }, [])

  useEffect(() => {
    if (!abierto || cargadoRef.current) return
    cargadoRef.current = true
    getToddChat(token)
      .then(d => {
        if (aliveRef.current) setMensajes(d.mensajes)
      })
      .catch(() => {
        /* tolerante a fallo: arrancamos con historial vacío */
      })
  }, [abierto, token])

  useEffect(() => {
    if (abierto) finRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [mensajes, enviando, abierto])

  const enviar = async () => {
    const msg = texto.trim()
    if (!msg || enviando) return
    setTexto("")
    setMensajes(prev => [...prev, { role: "user", content: msg }])
    setEnviando(true)
    try {
      const d = await enviarToddResponsable(token, msg)
      if (aliveRef.current) setMensajes(d.mensajes)
    } catch {
      if (aliveRef.current) {
        setMensajes(prev => [
          ...prev,
          {
            role: "todd",
            content:
              "Ahorita no pude responder. Intenta de nuevo en un momento, por favor.",
          },
        ])
      }
    } finally {
      if (aliveRef.current) setEnviando(false)
    }
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      void enviar()
    }
  }

  return (
    <>
      {!abierto && (
        <button
          type="button"
          onClick={() => setAbierto(true)}
          className="fixed bottom-5 right-5 z-40 rounded-full px-5 py-3 text-sm font-semibold text-white shadow-lg transition-transform hover:scale-105"
          style={{ backgroundColor: NAVY }}
        >
          Pregúntale a Todd
        </button>
      )}

      {abierto && (
        <div
          className="fixed bottom-5 right-5 z-50 flex h-[32rem] max-h-[80vh] w-[22rem] max-w-[calc(100vw-2.5rem)] flex-col overflow-hidden rounded-2xl border border-black/10 bg-white shadow-2xl"
        >
          <div
            className="flex items-center justify-between px-4 py-3"
            style={{ backgroundColor: NAVY }}
          >
            <div>
              <p className="text-sm font-semibold text-white">Todd — tu asistente</p>
              <p className="text-xs text-white/70">Dudas sobre tus tareas</p>
            </div>
            <button
              type="button"
              onClick={() => setAbierto(false)}
              aria-label="Cerrar"
              className="rounded-full p-1 text-white/80 transition-colors hover:text-white"
            >
              <span className="text-lg leading-none">×</span>
            </button>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto p-4" style={{ backgroundColor: BONE }}>
            {mensajes.length === 0 && !enviando && (
              <p className="text-sm text-gray-500">
                Hola, soy Todd. Pregúntame lo que necesites sobre tus tareas: cómo hacerlas,
                por dónde empezar o qué significan.
              </p>
            )}
            {mensajes.map((m, i) => {
              const esUsuario = m.role === "user"
              return (
                <div key={i} className={esUsuario ? "flex justify-end" : "flex justify-start"}>
                  <div
                    className="max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm"
                    style={
                      esUsuario
                        ? { backgroundColor: NAVY, color: "#ffffff" }
                        : { backgroundColor: "#ffffff", color: "#374151", border: "1px solid rgba(0,0,0,0.06)" }
                    }
                  >
                    {m.content}
                  </div>
                </div>
              )
            })}
            {enviando && (
              <div className="flex justify-start">
                <div className="rounded-2xl bg-white px-3 py-2 text-sm text-gray-500 border border-black/5">
                  Todd está escribiendo…
                </div>
              </div>
            )}
            <div ref={finRef} />
          </div>

          <div className="flex items-center gap-2 border-t border-black/5 bg-white p-3">
            <input
              type="text"
              value={texto}
              onChange={e => setTexto(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Escribe tu pregunta…"
              disabled={enviando}
              className="flex-1 rounded-xl border px-3 py-2 text-sm outline-none disabled:opacity-60"
              style={{ borderColor: "#dfe3ea", color: NAVY }}
            />
            <button
              type="button"
              onClick={() => void enviar()}
              disabled={enviando || !texto.trim()}
              className="rounded-xl px-4 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-40"
              style={{ backgroundColor: NAVY }}
            >
              Enviar
            </button>
          </div>
        </div>
      )}
    </>
  )
}

export default function EscritorioPage() {
  const params = useParams<{ token: string }>()
  const token = params.token
  const [data, setData] = useState<Escritorio | null>(null)
  const [notFound, setNotFound] = useState(false)
  const aliveRef = useRef(true)

  // Recarga las tareas (al subir un documento y mientras el Auditor lo lee).
  const [tick, setTick] = useState(0)
  const recargar = () => setTick(t => t + 1)

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
  }, [token, tick])

  // Mientras el Auditor lee algún documento, se vuelve a consultar cada 6 s hasta tener el resultado.
  const hayRevisando = !!data?.tareas.some(t => t.validacion?.estado === "revisando")
  useEffect(() => {
    if (!hayRevisando) return
    const id = window.setTimeout(recargar, 6000)
    return () => window.clearTimeout(id)
  }, [hayRevisando, tick])

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
            Estas son las tareas que te asignaron. Toca una para ver de qué trata y cómo hacerla, y sube
            en cada una el documento que demuestra el avance.
          </p>
        </header>

        {data.tareas.length === 0 ? (
          <div className="rounded-2xl border border-black/5 bg-white p-8 text-center text-sm text-gray-500">
            Aún no tienes tareas asignadas.
          </div>
        ) : (
          <div className="space-y-3">
            {data.tareas.map(t => (
              <TarjetaTarea key={t.id} token={token} tarea={t} onCambio={recargar} />
            ))}
          </div>
        )}
      </div>
      <ToddChat token={token} />
    </main>
  )
}
