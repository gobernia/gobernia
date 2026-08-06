import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Política de cookies — Gobernia",
  description: "Qué cookies usa Gobernia y para qué.",
}

// BORRADOR para revisión del cliente/abogado.
export default function CookiesPage() {
  return (
    <>
      <h1>Política de cookies</h1>
      <p><strong>Última actualización:</strong> 6 de agosto de 2026</p>

      <p>
        Una cookie es un pequeño archivo que se guarda en tu navegador cuando visitas un sitio.
        Gobernia utiliza únicamente las cookies necesarias para que la plataforma funcione.
      </p>

      <h2>1. Cookies que usamos</h2>
      <ul>
        <li>
          <strong>Cookies esenciales de sesión y autenticación:</strong> mantienen tu sesión
          iniciada de forma segura y permiten que la plataforma reconozca tu cuenta mientras la
          usas. Sin ellas el servicio no puede funcionar, por lo que no requieren consentimiento y
          no pueden desactivarse desde la plataforma.
        </li>
      </ul>
      <p>
        Actualmente <strong>no utilizamos cookies de publicidad ni de rastreo de terceros</strong>.
        Si esto cambia, actualizaremos esta política y te lo informaremos antes de activarlas.
      </p>

      <h2>2. Cómo gestionarlas</h2>
      <p>
        Puedes borrar o bloquear cookies desde la configuración de tu navegador. Ten en cuenta que,
        si bloqueas las cookies esenciales, no podrás iniciar sesión ni usar la plataforma.
      </p>

      <h2>3. Cambios a esta política</h2>
      <p>
        Publicaremos aquí cualquier actualización, indicando la fecha de última modificación.
      </p>

      <h2>4. Contacto</h2>
      <p>
        Dudas sobre esta política: <strong>[privacidad@gobernia.mx]</strong>. Más detalle sobre el
        tratamiento de tus datos en el <a href="/legal/privacidad">Aviso de privacidad</a>.
      </p>
    </>
  )
}
