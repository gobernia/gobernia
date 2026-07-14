"use client"

import { useEffect, useRef, useState } from "react"
import { motion } from "framer-motion"
import {
  Loader2, Users, Copy, Trash2, Link2, ArrowRight, Check,
  AlertTriangle, ShieldAlert, Eye, MessageCircleMore,
} from "lucide-react"
import {
  createInvite, listInvites, revokeInvite, consolidarPerspectivas, getSintesis,
  ROLE_LABEL, ANONYMOUS_ROLES, type Invite, type Sintesis, type Role,
} from "@/lib/perspectivas"
import { PageShell, PageHeader, Prose } from "@/components/ui/PageShell"

const ROLES = Object.keys(ROLE_LABEL) as Role[]

const STATUS_LABEL: Record<Invite["status"], string> = {
  pending: "Pendiente", active: "Activo", done: "Respondió",
}
const STATUS_CHIP: Record<Invite["status"], string> = {
  pending: "text-gray-500 bg-gray-50",
  active: "text-[var(--gob-navy)] bg-blue-50",
  done: "text-green-700 bg-green-50",
}

function inviteUrl(invite: Invite) {
  if (typeof window === "undefined") return invite.url ?? `/p/${invite.token}`
  return invite.url
    ? `${location.origin}${invite.url.startsWith("/") ? "" : "/"}${invite.url}`
    : `${location.origin}/p/${invite.token}`
}

export default function PerspectivasPage() {
  const [invites, setInvites] = useState<Invite[] | null>(null)
  const [sintesis, setSintesis] = useState<Sintesis | null>(null)
  const [role, setRole] = useState<Role>(ROLES[0])
  const [name, setName] = useState("")
  const [creating, setCreating] = useState(false)
  const [createErr, setCreateErr] = useState<string | null>(null)
  const [consolidando, setConsolidando] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [revokingId, setRevokingId] = useState<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const aliveRef = useRef(true)

  const needsName = !ANONYMOUS_ROLES.includes(role)

  const stopPolling = () => {
    if (timer.current) { clearTimeout(timer.current); timer.current = null }
  }

  const pollSintesis = () => {
    stopPolling()
    timer.current = setTimeout(async () => {
      try {
        const s = await getSintesis()
        if (!aliveRef.current) return
        setSintesis(s)
        if (s.status === "generating") pollSintesis()
      } catch { /* reintenta en el próximo ciclo */ }
    }, 3000)
  }

  const init = async () => {
    try {
      const [inv, s] = await Promise.all([listInvites(), getSintesis()])
      if (!aliveRef.current) return
      setInvites(inv)
      setSintesis(s)
      if (s.status === "generating") pollSintesis()
    } catch { if (aliveRef.current) setInvites([]) }
  }

  useEffect(() => {
    aliveRef.current = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    init()
    return () => { aliveRef.current = false; stopPolling() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const onCreate = async () => {
    setCreating(true); setCreateErr(null)
    try {
      const invite = await createInvite(role, needsName ? name.trim() || undefined : undefined)
      setInvites(prev => [invite, ...(prev ?? [])])
      setName("")
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setCreateErr(detail ?? "No se pudo crear el link. Intenta de nuevo.")
    } finally {
      setCreating(false)
    }
  }

  const onCopy = async (invite: Invite) => {
    try {
      await navigator.clipboard.writeText(inviteUrl(invite))
      setCopiedId(invite.id)
      setTimeout(() => setCopiedId(id => (id === invite.id ? null : id)), 2000)
    } catch { /* clipboard no disponible */ }
  }

  const onRevoke = async (id: string) => {
    setRevokingId(id)
    try {
      await revokeInvite(id)
      setInvites(prev => (prev ?? []).filter(i => i.id !== id))
    } catch { /* noop */ } finally { setRevokingId(null) }
  }

  const onConsolidar = async () => {
    setConsolidando(true)
    try {
      await consolidarPerspectivas()
      const s = await getSintesis()
      setSintesis(s)
      if (s.status === "generating") pollSintesis()
    } catch { /* noop */ } finally { setConsolidando(false) }
  }

  const generating = sintesis?.status === "generating" || consolidando
  const hasInvites = (invites?.length ?? 0) > 0

  return (
    <div className="min-h-dvh bg-white text-black">
      <PageHeader
        eyebrow="Escucha externa"
        title="Perspectivas"
        actions={hasInvites ? (
          <button onClick={onConsolidar} disabled={generating}
            className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-4 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-50 shrink-0">
            {generating ? <><Loader2 className="h-4 w-4 animate-spin" /> Consolidando…</> : <>
              Consolidar perspectivas <ArrowRight className="h-4 w-4" />
            </>}
          </button>
        ) : undefined}
      />

      <main>
      <PageShell className="py-10 space-y-10">

        {/* Formulario de invitación */}
        <section className="border border-gray-100 rounded-2xl p-5 sm:p-6 space-y-4">
          <div className="flex items-center gap-2.5">
            <span className="h-7 w-7 rounded-lg flex items-center justify-center text-[var(--gob-navy)] bg-blue-50">
              <Link2 className="h-4 w-4" />
            </span>
            <h2 className="text-sm font-bold tracking-wide uppercase">Invitar a alguien</h2>
          </div>
          <Prose>
            <p className="text-sm text-gray-500 leading-relaxed">
              Crea un link para que otra persona comparta su perspectiva del negocio a través de una breve
              conversación con Todd. Empleados y clientes responden de forma anónima.
            </p>
          </Prose>

          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="role" className="text-xs font-medium text-gray-500">Rol</label>
              <select id="role" value={role} onChange={e => setRole(e.target.value as Role)}
                className="border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm bg-white min-w-[180px] focus:outline-none focus:border-[var(--gob-navy)]">
                {ROLES.map(r => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
              </select>
            </div>

            {needsName && (
              <div className="flex flex-col gap-1.5">
                <label htmlFor="name" className="text-xs font-medium text-gray-500">Nombre (opcional)</label>
                <input id="name" value={name} onChange={e => setName(e.target.value)}
                  placeholder="Ej. María Pérez"
                  className="border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm min-w-[200px] focus:outline-none focus:border-[var(--gob-navy)]" />
              </div>
            )}

            <button onClick={onCreate} disabled={creating}
              className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-4 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-50">
              {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link2 className="h-4 w-4" />}
              Crear link
            </button>
          </div>
          {createErr && <p className="text-xs text-red-500">{createErr}</p>}
        </section>

        {/* Lista de invitaciones */}
        <section className="space-y-3">
          <h2 className="text-sm font-bold tracking-wide uppercase text-gray-500">Invitaciones</h2>

          {!invites && (
            <div className="border border-gray-100 rounded-2xl p-12 flex items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-gray-300" />
            </div>
          )}

          {invites && invites.length === 0 && (
            <div className="border border-gray-100 rounded-2xl p-10 flex flex-col items-center justify-center text-center gap-2">
              <Users className="h-5 w-5 text-gray-300" />
              <p className="text-sm text-gray-500">Aún no has invitado a nadie. Crea tu primer link arriba.</p>
            </div>
          )}

          {invites && invites.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-2.5">
              {invites.map(invite => (
                <motion.div key={invite.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                  className="border border-gray-100 rounded-2xl px-4 py-3 flex items-center gap-3 flex-wrap">
                  <div className="min-w-0 flex-1 flex items-center gap-3">
                    <span className="text-sm font-medium text-black shrink-0">{ROLE_LABEL[invite.role]}</span>
                    {invite.invitee_name && (
                      <span className="text-sm text-gray-500 truncate">{invite.invitee_name}</span>
                    )}
                    <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full shrink-0 ${STATUS_CHIP[invite.status]}`}>
                      {STATUS_LABEL[invite.status]}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button onClick={() => onCopy(invite)}
                      className="inline-flex items-center gap-1.5 border border-gray-200 text-xs font-medium text-gray-700 px-3 py-2 rounded-lg hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] transition-colors">
                      {copiedId === invite.id ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                      {copiedId === invite.id ? "Copiado" : "Copiar"}
                    </button>
                    <button onClick={() => onRevoke(invite.id)} disabled={revokingId === invite.id}
                      className="inline-flex items-center gap-1.5 border border-gray-200 text-xs font-medium text-red-500 px-3 py-2 rounded-lg hover:border-red-300 hover:bg-red-50 transition-colors disabled:opacity-50">
                      {revokingId === invite.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                      Revocar
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </section>

        {/* Síntesis */}
        {sintesis?.status === "generating" && (
          <div className="border border-gray-100 rounded-2xl p-16 flex flex-col items-center justify-center gap-3 text-center">
            <Loader2 className="h-6 w-6 animate-spin text-gray-300" />
            <p className="text-sm text-gray-500">Todd está cruzando las perspectivas recibidas…</p>
          </div>
        )}

        {sintesis?.status === "failed" && (
          <div className="border border-gray-100 rounded-2xl p-12 text-center text-sm text-gray-500">
            No se pudo generar la síntesis. Vuelve a intentar consolidar las perspectivas.
          </div>
        )}

        {sintesis?.status === "active" && (
          <section className="space-y-6 pt-2">
            <h2 className="text-xl font-bold tracking-tight">Síntesis de perspectivas</h2>

            {/* Su forma natural: tres lecturas en paralelo, no apiladas. */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 items-start">
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                className="border border-gray-100 border-t-4 border-t-green-500 rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="h-7 w-7 rounded-lg flex items-center justify-center text-green-700 bg-green-50">
                    <Check className="h-4 w-4" />
                  </span>
                  <h3 className="text-sm font-bold tracking-wide uppercase">Coincidencias</h3>
                </div>
                {sintesis.coincidencias.length > 0 ? (
                  <ul className="space-y-2">
                    {sintesis.coincidencias.map((t, i) => (
                      <li key={i} className="text-sm text-gray-700 leading-snug flex gap-2">
                        <span className="text-gray-300">•</span><span>{t}</span>
                      </li>
                    ))}
                  </ul>
                ) : <p className="text-xs text-gray-300 italic">Sin elementos.</p>}
              </motion.div>

              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
                className="border border-red-200 bg-red-50/40 border-t-4 border-t-red-500 rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="h-7 w-7 rounded-lg flex items-center justify-center text-red-700 bg-red-100">
                    <AlertTriangle className="h-4 w-4" />
                  </span>
                  <h3 className="text-sm font-bold tracking-wide uppercase text-red-700">Contradicciones</h3>
                </div>
                {sintesis.contradicciones.length > 0 ? (
                  <ul className="space-y-2">
                    {sintesis.contradicciones.map((t, i) => (
                      <li key={i} className="text-sm text-red-800 leading-snug flex gap-2">
                        <span className="text-red-300">•</span><span>{t}</span>
                      </li>
                    ))}
                  </ul>
                ) : <p className="text-xs text-gray-300 italic">Sin elementos.</p>}
              </motion.div>

              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
                className="border border-amber-200 bg-amber-50/40 border-t-4 border-t-amber-500 rounded-2xl p-5 md:col-span-2 lg:col-span-1">
                <div className="flex items-center gap-2 mb-3">
                  <span className="h-7 w-7 rounded-lg flex items-center justify-center text-amber-700 bg-amber-100">
                    <ShieldAlert className="h-4 w-4" />
                  </span>
                  <h3 className="text-sm font-bold tracking-wide uppercase text-amber-700">Puntos ciegos</h3>
                </div>
                {sintesis.puntos_ciegos.length > 0 ? (
                  <ul className="space-y-2">
                    {sintesis.puntos_ciegos.map((t, i) => (
                      <li key={i} className="text-sm text-amber-900 leading-snug flex gap-2">
                        <span className="text-amber-400">•</span><span>{t}</span>
                      </li>
                    ))}
                  </ul>
                ) : <p className="text-xs text-gray-300 italic">Sin elementos.</p>}
              </motion.div>
            </div>

            {Object.keys(sintesis.por_rol).length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="h-7 w-7 rounded-lg flex items-center justify-center text-[var(--gob-navy)] bg-blue-50">
                    <MessageCircleMore className="h-4 w-4" />
                  </span>
                  <h3 className="text-sm font-bold tracking-wide uppercase">Por rol</h3>
                </div>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3 items-start">
                  {Object.entries(sintesis.por_rol).map(([r, texto]) => (
                    <div key={r} className="border border-gray-100 rounded-2xl p-5">
                      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                        {ROLE_LABEL[r as Role] ?? r}
                      </p>
                      <p className="text-sm text-gray-700 leading-relaxed">{texto}</p>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-400 flex items-center gap-1.5 pt-1">
                  <Eye className="h-3.5 w-3.5" />
                  Los roles anónimos (empleado, cliente) se agrupan para proteger la identidad de cada persona.
                </p>
              </div>
            )}
          </section>
        )}
      </PageShell>
      </main>
    </div>
  )
}
