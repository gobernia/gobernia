# Fase 1 — Modal de bienvenida del Secretario — Diseño

**Fecha:** 2026-06-15
**Alcance:** Solo frontend (`frontend/`). Cero cambios de backend.

## Goal

Un modal de bienvenida en el dashboard donde el "Secretario del Consejo" se presenta y guía al usuario a completar el onboarding existente. Tiene dos modos: versión completa la primera vez, y un recordatorio corto en visitas posteriores mientras el onboarding siga incompleto.

## Architecture

Un componente nuevo `SecretarioWelcome.tsx` se monta en el Inicio del dashboard (`dashboard/page.tsx`). En cada carga decide si mostrarse y en qué modo, a partir de dos señales: si el onboarding está completo (`completedStages.length >= 8`) y si el usuario ya vio la versión completa (bandera en `localStorage` por usuario). El cierre del recordatorio se recuerda por sesión (`sessionStorage`) para no repetir en la misma visita. No toca backend: la completitud de KPIs ("no sé") ya está blindada en la generación de plan/sesión (la compuerta devuelve 400 y la página correspondiente muestra "Completa tus datos").

## Tech Stack

Next.js 16 App Router (client component; ver `frontend/AGENTS.md`), TypeScript, framer-motion (mismo patrón visual que los modales existentes en `dashboard/page.tsx`), lucide-react, Tailwind v4 (`--gob-navy`/`--gob-bone`/`--gob-ink`).

---

## Componente — `SecretarioWelcome.tsx`

**Crear:** `frontend/src/components/dashboard/SecretarioWelcome.tsx`

### Props
```ts
{
  onboardingComplete: boolean   // completedStages.length >= 8
  nextStageHref: string         // a dónde van "Empezar"/"Continuar" (siguiente etapa pendiente)
  userKey: string               // identificador del usuario (email) para la clave de localStorage
}
```

### Lógica de visibilidad (en `useEffect` al montar)
- Si `onboardingComplete` → no mostrar.
- Si `userKey` está vacío (aún no carga el usuario) → no mostrar todavía (esperar).
- Claves:
  - `localStorage["gobernia_secretario_welcome_seen_" + userKey]` → `"1"` cuando ya vio la versión completa.
  - `sessionStorage["gobernia_secretario_welcome_dismissed"]` → `"1"` cuando cerró el modal en esta sesión.
- Decisión:
  - Si `sessionStorage` marca cerrado en esta sesión → no mostrar.
  - Si no vio la versión completa (`localStorage` no está) → mostrar **modo completo**; al mostrarse, marcar `localStorage` = `"1"` (para que las siguientes veces sea recordatorio).
  - Si ya vio la versión completa pero el onboarding sigue incompleto → mostrar **modo recordatorio**.

### Contenido — modo completo
- Ícono/identidad del Secretario (usar `Sparkles` de lucide o el `GoberniaLogo`, consistente con los modales actuales).
- Título: **"Soy el Secretario de tu consejo"**.
- Cuerpo: *"Para que tus consejeros trabajen con tu empresa, necesito que completes tu información: empresa, equipo, prioridades, KPIs y gobierno. Toma unos minutos y se hace una sola vez."*
- Botones: **"Empezar"** (`Link` a `nextStageHref`) y **"Más tarde"** (cierra → marca `sessionStorage`).

### Contenido — modo recordatorio
- Mismo contenedor, texto corto.
- Título: **"Aún falta completar tus datos"**.
- Cuerpo: *"Para activar tu consejo necesito que termines tu información. Continúa donde lo dejaste."*
- Botones: **"Continuar"** (`Link` a `nextStageHref`) y **"Más tarde"** (cierra → marca `sessionStorage`).

### Comportamiento de botones
- "Empezar"/"Continuar": navega a `nextStageHref` (un `Link`; al hacer clic también cierra el modal). El `localStorage` ya quedó marcado al mostrarse el modo completo.
- "Más tarde" / clic en el backdrop / botón cerrar (X): cierra el modal y marca `sessionStorage["gobernia_secretario_welcome_dismissed"] = "1"` para no reaparecer en esta sesión. Reaparece en la siguiente visita (modo recordatorio) si sigue incompleto.

### Estilo
Reusar el patrón visual de los modales de `dashboard/page.tsx`: backdrop `fixed inset-0 z-50 bg-black/30 backdrop-blur-sm` con `motion.div` de entrada/salida (`AnimatePresence`), tarjeta centrada `fixed z-50 inset-x-4 top-1/2 -translate-y-1/2 max-w-sm mx-auto bg-white rounded-2xl shadow-xl p-8 space-y-5`, botón primario `bg-[var(--gob-navy)] text-[var(--gob-bone)]`. `EASE: [0.22, 1, 0.36, 1]`.

---

## Integración — `dashboard/page.tsx`

**Modificar:** `frontend/src/app/dashboard/page.tsx`

- Importar y montar `<SecretarioWelcome>` dentro del render del dashboard (junto a los demás modales / al inicio del árbol), pasando:
  - `onboardingComplete={onboardingComplete}` (ya existe en el componente).
  - `nextStageHref={nextEtapa ? \`/onboarding/etapa-${nextEtapa.n}\` : "/onboarding/etapa-1"}` (reusa `nextEtapa`, ya calculado).
  - `userKey={userEmail ?? ""}` (ya existe `userEmail` en estado).
- No se elimina el banner de onboarding ni el modal "Configura tu empresa" (`showSetupModal`): el modal del Secretario es la bienvenida de arriba; los demás se quedan como están.

---

## Out of scope (NO se toca)

- Backend completo. (La completitud de KPIs ya está blindada en la generación de plan/sesión; el modal solo usa la señal de 8 etapas.)
- El banner de onboarding del Inicio y el modal de setup por acción (`showSetupModal`) — se conservan.
- Cualquier persona/IA del Secretario en backend (este modal es estático, no llama a la IA).

## Decisiones tomadas

- **Disparo:** primera vez (versión completa) + recordatorio en visitas posteriores mientras falten datos. (Elegido por el usuario.)
- **Señal de "faltan datos":** solo las 8 etapas (`completedStages.length >= 8`), sin tocar backend. (Elegido por el usuario.)
- **Copia:** la propuesta arriba (aprobada por el usuario; pulible después).
- **Persistencia:** `localStorage` por usuario para "ya vio la versión completa"; `sessionStorage` para "cerrado en esta sesión".

## Testing

Frontend sin suite de pruebas de UI. Verificación:
1. `npm run lint` + `npm run build` pasan.
2. Smoke manual con un usuario de **onboarding incompleto** (ej. una cuenta recién registrada en `/sign-up`; `djbeuvrin@gmail.com` NO sirve porque tiene el onboarding completo y el modal no debe aparecerle):
   - Primera carga del dashboard → aparece el **modo completo**.
   - Recargar → aparece el **modo recordatorio** (ya marcó `localStorage`).
   - "Más tarde" → cierra y NO reaparece al navegar dentro de la misma sesión.
   - Nueva sesión / recarga después → reaparece el recordatorio.
   - Con un usuario de onboarding **completo** (djbeuvrin) → el modal NO aparece.
   - "Empezar"/"Continuar" → navega a la etapa pendiente del onboarding.
