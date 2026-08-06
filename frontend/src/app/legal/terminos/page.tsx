import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Términos y condiciones — Gobernia",
  description: "Condiciones de uso de la plataforma Gobernia.",
}

// BORRADOR para revisión del cliente/abogado. Los datos entre [corchetes]
// deben completarse antes de publicar en producción.
export default function TerminosPage() {
  return (
    <>
      <h1>Términos y condiciones</h1>
      <p><strong>Última actualización:</strong> 6 de agosto de 2026</p>

      <p>
        Estos términos regulan el uso de la plataforma <strong>Gobernia</strong>, operada por
        <strong> [Razón social de la empresa]</strong>, con domicilio en
        <strong> [domicilio fiscal completo]</strong>, Ciudad de México, México. Al crear una cuenta
        o usar la plataforma aceptas estos términos; si no estás de acuerdo, no utilices el servicio.
      </p>

      <h2>1. El servicio</h2>
      <p>
        Gobernia es un copiloto de gobierno corporativo: cinco consejeros con inteligencia
        artificial analizan la información que proporcionas sobre tu empresa y generan diagnósticos,
        planes, sesiones de consejo y seguimiento de tareas. El servicio está dirigido a empresas y
        profesionales; al usarlo declaras que lo haces en nombre de una empresa y que tienes
        facultades para ello.
      </p>

      <h2>2. Gobernia no sustituye asesoría profesional</h2>
      <p>
        Los análisis, diagnósticos y recomendaciones se generan con inteligencia artificial y tienen
        una finalidad <strong>informativa y de apoyo a la decisión</strong>. No constituyen asesoría
        legal, fiscal, contable, financiera ni de inversión, y no sustituyen a un consejo de
        administración humano ni a profesionales certificados.
        <strong> Las decisiones que tomes con base en la plataforma son tu responsabilidad.</strong>
        La IA puede producir información incompleta o inexacta; verifica cualquier resultado
        relevante antes de actuar.
      </p>

      <h2>3. Tu cuenta</h2>
      <ul>
        <li>Debes proporcionar información veraz y mantener la confidencialidad de tus credenciales.</li>
        <li>Eres responsable de la actividad que ocurra en tu cuenta.</li>
        <li>Notifícanos de inmediato cualquier uso no autorizado en <strong>[hola@gobernia.mx]</strong>.</li>
      </ul>

      <h2>4. Uso aceptable</h2>
      <ul>
        <li>No uses la plataforma para fines ilícitos ni para dañar a terceros.</li>
        <li>No intentes vulnerar la seguridad, hacer ingeniería inversa ni acceder a datos de otros usuarios.</li>
        <li>No cargues contenido del que no tengas derechos o que infrinja derechos de terceros.</li>
        <li>No revendas ni sublicencies el servicio sin autorización escrita de Gobernia.</li>
      </ul>

      <h2>5. Tu información y propiedad intelectual</h2>
      <p>
        La información de tu empresa que cargas a la plataforma <strong>es tuya</strong>. Nos
        otorgas una licencia limitada para procesarla con el único fin de prestarte el servicio.
        Los resultados generados para tu empresa (diagnósticos, planes, actas) son tuyos para tu uso
        interno. La plataforma, su software, marca, diseño y contenido propio son propiedad de
        Gobernia y están protegidos por las leyes de propiedad intelectual.
      </p>

      <h2>6. Confidencialidad y seguridad</h2>
      <p>
        Tratamos la información de tu empresa como confidencial: viaja cifrada, se almacena cifrada
        y no se usa para entrenar modelos de IA ni se comparte con terceros para fines comerciales.
        El detalle está en nuestro <a href="/legal/privacidad">Aviso de privacidad</a>.
      </p>

      <h2>7. Planes y pagos</h2>
      <p>
        Las condiciones comerciales (precios, planes, periodos de prueba, facturación y cancelación)
        se informan en la plataforma al momento de contratar. <strong>[Completar cuando se definan
        los planes comerciales: precios, ciclo de facturación, política de reembolsos.]</strong>
      </p>

      <h2>8. Disponibilidad del servicio</h2>
      <p>
        Trabajamos para que la plataforma esté disponible de forma continua, pero no garantizamos
        disponibilidad ininterrumpida: puede haber mantenimientos, actualizaciones o fallas ajenas a
        nuestro control. Podremos modificar o mejorar funciones del servicio; si un cambio afecta de
        forma sustancial lo contratado, te lo notificaremos.
      </p>

      <h2>9. Limitación de responsabilidad</h2>
      <p>
        En la medida máxima permitida por la ley, Gobernia no será responsable por daños indirectos,
        lucro cesante o pérdida de datos derivados del uso o imposibilidad de uso del servicio. La
        responsabilidad total de Gobernia frente a ti se limita al monto pagado por el servicio en
        los doce meses anteriores al hecho que la origine.
      </p>

      <h2>10. Terminación</h2>
      <p>
        Puedes cancelar tu cuenta en cualquier momento. Gobernia podrá suspender o terminar el
        acceso en caso de incumplimiento de estos términos, notificándote la causa. A la
        terminación, aplicará lo previsto en el Aviso de privacidad sobre conservación y eliminación
        de datos.
      </p>

      <h2>11. Modificaciones a estos términos</h2>
      <p>
        Podremos actualizar estos términos; publicaremos la versión vigente con su fecha de última
        actualización y, si el cambio es significativo, te lo notificaremos con anticipación
        razonable. El uso continuado del servicio implica la aceptación de la versión vigente.
      </p>

      <h2>12. Ley aplicable y jurisdicción</h2>
      <p>
        Estos términos se rigen por las leyes de los Estados Unidos Mexicanos. Para cualquier
        controversia, las partes se someten a los tribunales competentes de la Ciudad de México,
        renunciando a cualquier otro fuero.
      </p>

      <h2>13. Contacto</h2>
      <p>Dudas sobre estos términos: <strong>[hola@gobernia.mx]</strong>.</p>
    </>
  )
}
