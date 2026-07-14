"use client"

import { useEffect, useRef, useState } from "react"
import { ChevronDown, FileText, Upload, X } from "lucide-react"
import {
  BOARD_DOC_TYPES,
  BoardDoc,
  BoardDocType,
  deleteBoardDoc,
  listBoardDocs,
  uploadBoardDoc,
} from "@/lib/boardDocs"

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.xlsx,.xls,.docx"
const UNREADABLE = /\.(xlsx|xls|docx|doc)$/i

function formatDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ""
  return d.toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" })
}

function typeLabel(doc: BoardDoc): string {
  if (doc.document_type_label) return doc.document_type_label
  return BOARD_DOC_TYPES.find(t => t.value === doc.document_type)?.label ?? doc.document_type
}

export default function BoardPack({
  sessionId,
  collapsible = false,
}: {
  sessionId: string
  collapsible?: boolean
}) {
  const [items,   setItems]   = useState<BoardDoc[]>([])
  const [docType, setDocType] = useState<BoardDocType>("financial")
  const [busy,    setBusy]    = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const [warning, setWarning] = useState<string | null>(null)
  const [open,    setOpen]    = useState(!collapsible)

  const inputRef = useRef<HTMLInputElement>(null)
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    listBoardDocs(sessionId)
      .then(list => {
        if (!aliveRef.current) return
        setItems(list)
      })
      .catch(() => {})
    return () => { aliveRef.current = false }
  }, [sessionId])

  const apply = (list: BoardDoc[]) => setItems(list)

  const onPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setBusy(true)
    setError(null)
    setWarning(
      UNREADABLE.test(file.name)
        ? "Los Excel y Word no se pueden leer: súbelos en PDF. Tu consejo verá que existe el archivo, pero no podrá leer su contenido."
        : null,
    )
    try {
      const doc = await uploadBoardDoc(sessionId, file, docType)
      apply([...items, doc])
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? "No se pudo subir el documento.")
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ""
    }
  }

  const onRemove = async (id: string) => {
    apply(items.filter(i => i.id !== id))
    await deleteBoardDoc(sessionId, id).catch(() =>
      listBoardDocs(sessionId).then(apply).catch(() => {}),
    )
  }

  return (
    <section className="border border-gray-100 rounded-2xl">
      {/* Header */}
      <div className="flex items-start gap-3 p-6">
        <div className="w-9 h-9 rounded-xl bg-[var(--gob-bone)] flex items-center justify-center flex-shrink-0">
          <FileText className="h-4 w-4 text-[var(--gob-navy)]" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-[var(--gob-ink)]">
            Documentos para el consejo
            {items.length > 0 && (
              <span className="ml-2 text-[10px] font-medium text-gray-400">{items.length}</span>
            )}
          </p>
          <p className="text-xs text-gray-400 mt-1 leading-relaxed">
            Sube los documentos que quieres que tu consejo lea antes de analizar (estados
            financieros, presentación, plan de auditoría). Cada consejero leerá lo que le compete.
          </p>
        </div>
        {collapsible && (
          <button
            type="button"
            onClick={() => setOpen(o => !o)}
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-[var(--gob-navy)] transition-colors flex-shrink-0"
          >
            {open ? "Ocultar" : "Ver"}
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} />
          </button>
        )}
      </div>

      {open && (
        <div className="px-6 pb-6 space-y-4">
          {/* Tipo de documento */}
          <div className="space-y-2">
            <p className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">
              Tipo de documento
            </p>
            <div className="flex flex-wrap gap-2">
              {BOARD_DOC_TYPES.map(t => (
                <button
                  key={t.value}
                  type="button"
                  title={t.hint}
                  onClick={() => setDocType(t.value)}
                  className={`px-3.5 py-2 rounded-xl text-xs font-medium border-2 transition-colors ${
                    docType === t.value
                      ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                      : "border-gray-200 text-gray-500 hover:border-gray-400 hover:text-[var(--gob-navy)]"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Lista */}
          <div className="space-y-1.5">
            {items.map(doc => (
              <div
                key={doc.id}
                className="flex items-center gap-3 bg-gray-50 rounded-xl px-3.5 py-2.5"
              >
                <FileText className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
                <span className="flex-1 truncate text-sm text-[var(--gob-ink)]">{doc.filename}</span>
                <span className="hidden sm:inline text-[10px] font-medium text-gray-400 whitespace-nowrap">
                  {typeLabel(doc)}
                </span>
                <span className="hidden md:inline text-[10px] text-gray-300 whitespace-nowrap">
                  {formatDate(doc.created_at)}
                </span>
                <button
                  type="button"
                  onClick={() => onRemove(doc.id)}
                  aria-label={`Eliminar ${doc.filename}`}
                  className="text-gray-300 hover:text-red-500 transition-colors flex-shrink-0"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}

            {items.length === 0 && (
              <div className="border border-dashed border-gray-200 rounded-xl px-4 py-6 text-center">
                <p className="text-xs text-gray-400 leading-relaxed">
                  Todavía no hay documentos. Sin ellos tu consejo analizará solo con el perfil de la
                  empresa; con ellos, cada hallazgo podrá citar su fuente.
                </p>
              </div>
            )}
          </div>

          {/* Subir */}
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            accept={ACCEPT}
            onChange={onPick}
          />
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={busy}
              onClick={() => inputRef.current?.click()}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--gob-navy)] border border-gray-200 hover:border-gray-400 px-3.5 py-2 rounded-xl transition-colors disabled:opacity-50"
            >
              <Upload className="h-3.5 w-3.5" />
              {busy ? "Subiendo…" : "Subir documento"}
            </button>
            <p className="text-[10px] text-gray-400">
              PDF e imágenes se leen completos. Los Excel y Word no se pueden leer: súbelos en PDF.
            </p>
          </div>

          {warning && (
            <p
              className="text-xs leading-relaxed rounded-xl px-3.5 py-2.5 bg-gray-50"
              style={{ color: "#b45309" }}
            >
              {warning}
            </p>
          )}
          {error && <p className="text-xs text-red-500">{error}</p>}
        </div>
      )}
    </section>
  )
}
