"use client"

import { useState, useRef } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { ChevronRight, Upload, FileText, Trash2, CheckCircle2 } from "lucide-react"
import ProgressBar from "@/components/onboarding/ProgressBar"
import GoberniaButton from "@/components/ui/GoberniaButton"
import { cn } from "@/lib/utils"
import { useOnboardingStore } from "@/lib/store"
import api from "@/lib/api"

const DOC_TYPES = [
  { value: "financial",        label: "Estados financieros" },
  { value: "org_chart",        label: "Organigrama" },
  { value: "bylaws",           label: "Acta constitutiva / Estatutos" },
  { value: "business_plan",    label: "Plan de negocios" },
  { value: "internal_rules",   label: "Reglamento interno" },
  { value: "family_protocol",  label: "Protocolo familiar" },
  { value: "other",            label: "Otro" },
]

interface UploadedDoc {
  document_id: string
  filename: string
  document_type_label: string
  file_size_kb: number
}

export default function Etapa7Page() {
  const router = useRouter()
  const fromDatos = useSearchParams().get("from") === "datos"
  const { sessionId, markStageComplete } = useOnboardingStore()
  const fileRef = useRef<HTMLInputElement>(null)
  const [docType, setDocType] = useState("financial")
  const [uploading, setUploading] = useState(false)
  const [completing, setCompleting] = useState(false)
  const [uploaded, setUploaded] = useState<UploadedDoc[]>([])
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const uploadFile = async (file: File) => {
    setUploading(true)
    setError(null)
    try {
      const form = new FormData()
      form.append("file", file)
      form.append("document_type", docType)
      const r = await api.post(`/onboarding/${sessionId}/etapa-7/upload`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      setUploaded(prev => [...prev, {
        document_id: r.data.document_id,
        filename: r.data.filename,
        document_type_label: r.data.document_type_label,
        file_size_kb: r.data.file_size_kb,
      }])
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? "No se pudo subir el archivo. Intenta de nuevo.")
    } finally {
      setUploading(false)
    }
  }

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return
    uploadFile(files[0])
  }

  const handleComplete = async () => {
    setCompleting(true)
    setError(null)
    try {
      await api.post(`/onboarding/${sessionId}/etapa-7/complete`)
      markStageComplete(7)
      router.push(fromDatos ? "/dashboard/datos" : "/onboarding/etapa-8")
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? "Ocurrió un error. Intenta de nuevo.")
    } finally {
      setCompleting(false)
    }
  }

  return (
    <div className="w-full max-w-xl space-y-8">
      <ProgressBar currentStep={7} />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        className="space-y-6"
      >
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-primary mb-3">
            <FileText className="h-5 w-5" />
            <span className="text-sm font-medium">Documentos</span>
          </div>
          <h1 className="text-2xl font-bold text-foreground leading-tight">
            Sube documentos de tu empresa
          </h1>
          <p className="text-sm text-muted-foreground">
            Tus agentes los analizarán para enriquecer el diagnóstico. PDF, Excel, Word o imagen. Máx 10 MB por archivo.
          </p>
        </div>

        {/* Tipo de documento */}
        <div className="space-y-2">
          <p className="text-sm font-medium text-foreground">Tipo de documento a subir</p>
          <div className="grid grid-cols-2 gap-2">
            {DOC_TYPES.map(dt => (
              <motion.button
                key={dt.value}
                type="button"
                whileTap={{ scale: 0.97 }}
                onClick={() => setDocType(dt.value)}
                className={cn(
                  "text-left px-3 py-2.5 rounded-xl border-2 text-xs font-medium transition-all duration-150",
                  docType === dt.value
                    ? "border-primary bg-primary/5 text-primary"
                    : "border-gray-200 text-foreground hover:border-primary/30"
                )}
              >
                {dt.label}
              </motion.button>
            ))}
          </div>
        </div>

        {/* Drop zone */}
        <div
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={e => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}
          onClick={() => fileRef.current?.click()}
          className={cn(
            "border-2 border-dashed rounded-2xl p-10 flex flex-col items-center justify-center gap-3 cursor-pointer transition-all duration-200",
            dragOver ? "border-primary bg-primary/5" : "border-gray-200 hover:border-primary/40 hover:bg-gray-50"
          )}
        >
          <Upload className={cn("h-8 w-8", dragOver ? "text-primary" : "text-gray-400")} />
          <div className="text-center">
            <p className="text-sm font-medium text-foreground">
              {uploading ? "Subiendo…" : "Arrastra el archivo aquí"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">o haz clic para seleccionar</p>
          </div>
          <input
            ref={fileRef}
            type="file"
            className="hidden"
            accept=".pdf,.docx,.xlsx,.xls,.png,.jpg,.jpeg"
            onChange={e => handleFiles(e.target.files)}
          />
        </div>

        {/* Uploaded docs */}
        <AnimatePresence>
          {uploaded.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Documentos subidos
              </p>
              {uploaded.map(doc => (
                <motion.div
                  key={doc.document_id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center gap-3 px-4 py-3 rounded-xl border-2 border-green-100 bg-green-50"
                >
                  <CheckCircle2 className="h-4 w-4 text-green-600 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">{doc.filename}</p>
                    <p className="text-xs text-muted-foreground">{doc.document_type_label} · {doc.file_size_kb} KB</p>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </AnimatePresence>

        {error && <p className="text-sm text-red-500 text-center">{error}</p>}

        <div className="flex gap-3">
          <GoberniaButton variant="ghost" onClick={() => router.push("/onboarding/etapa-6")} className="flex-1">
            Atrás
          </GoberniaButton>
          <GoberniaButton
            onClick={handleComplete}
            disabled={uploaded.length === 0}
            loading={completing}
            className="flex-[2]"
            size="lg"
          >
            Guardar y continuar <ChevronRight className="h-4 w-4" />
          </GoberniaButton>
        </div>

        {uploaded.length === 0 && (
          <p className="text-xs text-center text-muted-foreground">
            Debes subir al menos un documento para continuar.
          </p>
        )}
      </motion.div>
    </div>
  )
}
