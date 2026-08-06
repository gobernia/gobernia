import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Aviso de privacidad — Gobernia",
  description: "Cómo Gobernia recaba, usa y protege tus datos personales y la información de tu empresa.",
}

// BORRADOR para revisión del cliente/abogado. Los datos entre [corchetes]
// deben completarse antes de publicar en producción.
export default function AvisoPrivacidadPage() {
  return (
    <>
      <h1>Aviso de privacidad</h1>
      <p><strong>Última actualización:</strong> 6 de agosto de 2026</p>

      <h2>1. Responsable del tratamiento</h2>
      <p>
        <strong>[Razón social de la empresa]</strong> (en adelante, «<strong>Gobernia</strong>»),
        con domicilio en <strong>[domicilio fiscal completo]</strong>, Ciudad de México, México,
        es responsable del tratamiento de tus datos personales conforme a la Ley Federal de
        Protección de Datos Personales en Posesión de los Particulares (LFPDPPP), su Reglamento
        y los Lineamientos del Aviso de Privacidad.
      </p>

      <h2>2. Datos personales que recabamos</h2>
      <ul>
        <li><strong>Datos de identificación y contacto:</strong> nombre, correo electrónico y contraseña de acceso.</li>
        <li><strong>Información de tu empresa:</strong> la que proporcionas durante el onboarding y el uso de la plataforma — industria, estructura del equipo, prioridades estratégicas, indicadores, información financiera y operativa, y documentos que decidas cargar.</li>
        <li><strong>Datos de uso:</strong> registros técnicos de acceso y actividad en la plataforma (fecha, hora, acciones realizadas), necesarios para la seguridad y el funcionamiento del servicio.</li>
      </ul>
      <p>Gobernia no recaba datos personales sensibles (origen étnico, estado de salud, creencias, afiliación sindical, entre otros). Te pedimos no capturarlos en los campos de texto libre.</p>

      <h2>3. Finalidades del tratamiento</h2>
      <p><strong>Finalidades primarias</strong> (necesarias para el servicio):</p>
      <ul>
        <li>Crear y administrar tu cuenta y autenticar tu acceso.</li>
        <li>Prestar el servicio: generar diagnósticos, planes, sesiones del consejo con IA y demás funciones de la plataforma a partir de la información de tu empresa.</li>
        <li>Darte soporte y atender tus solicitudes.</li>
        <li>Cumplir obligaciones legales aplicables.</li>
      </ul>
      <p><strong>Finalidades secundarias</strong> (puedes oponerte sin que afecte el servicio):</p>
      <ul>
        <li>Enviarte comunicaciones sobre novedades y mejoras del producto.</li>
        <li>Elaborar estadísticas internas de uso, de forma agregada y disociada.</li>
      </ul>

      <h2>4. Uso de inteligencia artificial</h2>
      <p>
        Para generar los análisis, la información de tu empresa se procesa mediante modelos de
        inteligencia artificial de proveedores terceros que actúan como encargados del tratamiento,
        bajo acuerdos que prohíben usar tu información para fines propios.
        <strong> Tus datos no se utilizan para entrenar modelos de IA</strong> ni se comparten con
        terceros para fines comerciales.
      </p>

      <h2>5. Transferencias y encargados</h2>
      <p>
        Gobernia no vende ni renta tus datos personales. Compartimos información únicamente con
        proveedores que nos permiten operar el servicio (alojamiento e infraestructura en la nube,
        autenticación y base de datos, procesamiento de IA), quienes la tratan por cuenta de
        Gobernia y bajo obligaciones de confidencialidad. Fuera de estos casos, solo comunicaremos
        datos cuando lo exija una autoridad competente conforme a la ley.
      </p>

      <h2>6. Medidas de seguridad</h2>
      <p>
        Tu información viaja cifrada (HTTPS/TLS) y se almacena cifrada en reposo. El acceso a tu
        cuenta está protegido con autenticación y la información de tu empresa es confidencial:
        solo tú y tu consejo con IA la utilizan.
      </p>

      <h2>7. Derechos ARCO y revocación del consentimiento</h2>
      <p>
        Puedes ejercer en cualquier momento tus derechos de <strong>Acceso, Rectificación,
        Cancelación u Oposición</strong> (ARCO), así como revocar tu consentimiento o limitar el
        uso o divulgación de tus datos, escribiendo a
        <strong> [privacidad@gobernia.mx]</strong> con: (i) tu nombre y correo asociado a la cuenta,
        (ii) el derecho que deseas ejercer y (iii) una descripción clara de tu solicitud.
        Responderemos en los plazos que establece la LFPDPPP.
      </p>

      <h2>8. Conservación y eliminación</h2>
      <p>
        Conservamos tu información mientras tu cuenta esté activa. Si la cancelas, eliminaremos o
        anonimizaremos tus datos en un plazo razonable, salvo aquellos que debamos conservar por
        obligación legal.
      </p>

      <h2>9. Cookies</h2>
      <p>
        Usamos cookies esenciales para el funcionamiento de la plataforma (por ejemplo, mantener tu
        sesión iniciada). Consulta la <a href="/legal/cookies">Política de cookies</a> para más
        detalle.
      </p>

      <h2>10. Cambios a este aviso</h2>
      <p>
        Podremos actualizar este aviso para reflejar cambios legales o del servicio. Publicaremos la
        versión vigente en esta página indicando la fecha de última actualización y, si el cambio es
        significativo, te lo notificaremos dentro de la plataforma o por correo.
      </p>

      <h2>11. Contacto</h2>
      <p>
        Para cualquier duda sobre este aviso o el tratamiento de tus datos:
        <strong> [privacidad@gobernia.mx]</strong>.
      </p>
    </>
  )
}
