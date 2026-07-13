"use client"

import { useEffect, useRef, useState } from "react"
import { ImageIcon, Loader2, Trash2, Upload } from "lucide-react"
import { getLogo, uploadLogo, deleteLogo, LOGO_ACCEPT, LOGO_MAX_BYTES } from "@/lib/logo"

export default function LogoUpload({ companyName }: { companyName?: string | null }) {
  const [logo, setLogo] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    ;(async () => {
      try {
        const r = await getLogo()
        if (aliveRef.current) setLogo(r.logo)
      } catch { /* sin logo */ }
      finally { if (aliveRef.current) setLoading(false) }
    })()
    return () => { aliveRef.current = false }
  }, [])

  const onPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setError(null)

    if (file.size > LOGO_MAX_BYTES) {
      setError("La imagen pesa más de 1 MB. Sube una versión más ligera.")
      if (inputRef.current) inputRef.current.value = ""
      return
    }

    setBusy(true)
    try {
      const r = await uploadLogo(file)
      if (aliveRef.current) setLogo(r.logo)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      if (aliveRef.current) setError(msg ?? "No se pudo subir el logo.")
    } finally {
      if (aliveRef.current) setBusy(false)
      if (inputRef.current) inputRef.current.value = ""
    }
  }

  const onRemove = async () => {
    setBusy(true); setError(null)
    try {
      await deleteLogo()
      if (aliveRef.current) setLogo(null)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      if (aliveRef.current) setError(msg ?? "No se pudo quitar el logo.")
    } finally {
      if (aliveRef.current) setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-5">
        <div className="w-24 h-24 rounded-2xl border border-gray-200 bg-gray-50 flex items-center justify-center overflow-hidden shrink-0">
          {loading ? (
            <Loader2 className="h-5 w-5 text-gray-300 animate-spin" />
          ) : logo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logo} alt={companyName || "Logo de tu empresa"} className="max-w-full max-h-full object-contain" />
          ) : (
            <span className="flex flex-col items-center gap-1 text-gray-300">
              <ImageIcon className="h-6 w-6" />
              <span className="text-[10px] font-medium uppercase tracking-wide">Sin logo</span>
            </span>
          )}
        </div>

        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={busy || loading}
              onClick={() => inputRef.current?.click()}
              className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-4 py-2 rounded-xl hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-50"
            >
              {busy
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Subiendo…</>
                : <><Upload className="h-4 w-4" /> {logo ? "Cambiar logo" : "Subir logo"}</>}
            </button>
            {logo && !busy && (
              <button
                type="button"
                onClick={onRemove}
                className="inline-flex items-center gap-1.5 text-sm text-gray-500 px-3 py-2 rounded-xl hover:text-red-600 hover:bg-red-50 transition-colors"
              >
                <Trash2 className="h-4 w-4" /> Quitar
              </button>
            )}
          </div>
          <p className="text-xs text-gray-400 max-w-xs">
            PNG o JPG, máximo 1 MB. Se usará en tus reportes en PDF.
          </p>
        </div>
      </div>

      <input ref={inputRef} type="file" className="hidden" accept={LOGO_ACCEPT} onChange={onPick} />
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  )
}
