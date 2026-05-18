"""
Base de conocimiento de Gobernia — extraída de los PDFs del Centro Mexicano de la
Familia Empresaria, Consejo Coordinador Empresarial, y Todd Empresas de Familia.

Esta base se inyecta en el prompt de cada agente (CFO, CSO, CRO, Auditor) para
que sus análisis y recomendaciones estén fundamentados en los frameworks de
mejores prácticas de gobierno corporativo mexicano e internacional.

Fuentes:
- Código de Principios y Mejores Prácticas de Gobierno Corporativo (CCE, 2018)
- Código de Mejores Prácticas Corporativas 2024 (CCE)
- 10 temas prioritarios para los Consejos 2026 (Todd Empresas de Familia)
- La Nueva Era de las Empresas Familiares: Gobernanza e Innovación (Todd, 2024)
- Brochure TEdF 2024
"""


# ── Principios fundamentales (para todos los agentes) ────────────────────────

CORE_PRINCIPLES = """
PRINCIPIOS FUNDAMENTALES DE GOBIERNO CORPORATIVO (CCE México 2018, vigente 2024):

1. Trato igualitario, respeto y protección de los intereses de TODOS los accionistas.
2. Generación de valor económico Y social, considerando a los terceros interesados
   (clientes, proveedores, empleados, comunidad).
3. Emisión y revelación responsable de información — transparencia en la administración.
4. Conducción honesta y responsable de la sociedad.
5. Prevención de operaciones ilícitas y conflictos de interés.
6. Existencia de un Código de Ética formal.
7. Revelación de hechos indebidos y protección de los informantes (whistleblowers).
8. Aseguramiento del rumbo estratégico y vigilancia del desempeño de la administración.
9. Ejercicio de la responsabilidad fiduciaria del Consejo de Administración.
10. Identificación, administración, control y revelación de los riesgos estratégicos.
11. Cumplimiento de todas las disposiciones legales aplicables.
12. Dar certidumbre a accionistas, inversionistas y terceros sobre la conducción
    honesta y responsable de los negocios.

CONCEPTO BASE: "Gobierno Corporativo es el sistema bajo el cual las sociedades son
dirigidas y controladas". Distingue claramente:
- Consejo de Administración → define rumbo estratégico, vigila operación, aprueba gestión
- Director General → gestiona, conduce, ejecuta los negocios sujetándose al Consejo

Los 12 principios son aplicables a CUALQUIER sociedad: civil, mercantil, asistencial;
pública o privada; sin distinguir tamaño, actividad ni composición accionaria.
"""


# ── Mejores prácticas del Consejo (para todos los agentes) ────────────────────

BOARD_BEST_PRACTICES = """
INTEGRACIÓN Y FUNCIONAMIENTO DEL CONSEJO DE ADMINISTRACIÓN:

Composición recomendada:
- Entre 3 y 15 consejeros (rango óptimo de pluralidad sin perder eficiencia).
- AL MENOS 25% deben ser consejeros independientes.
- AL MENOS 60% del consejo debe ser independientes + patrimoniales (no funcionarios).
- Se recomienda explícitamente la inclusión de mujeres en el Consejo.
- Evitar consejeros suplentes; si los hay, deben heredar la independencia del propietario.

Criterios de INDEPENDENCIA — un consejero NO es independiente si:
- Es empleado o directivo (o lo fue en los últimos 12 meses)
- Tiene influencia significativa (≥20% del capital) o poder de mando
- Es asesor/consultor cuyos ingresos dependen >10% de la sociedad
- Es cliente/proveedor/deudor/acreedor importante (>10% de ventas o >15% de activos)
- Recibe donativos importantes (>15%) de la sociedad
- Es pariente (hasta 4° grado) de directivos
Un accionista sin influencia significativa puede ser "consejero patrimonial independiente".

ÓRGANOS INTERMEDIOS (comités) — cuatro funciones críticas:
1. Auditoría (presidido por independiente con conocimiento contable/financiero)
2. Evaluación y Compensación
3. Finanzas y Planeación
4. Riesgo y Cumplimiento
Cada comité: 3-7 miembros, ideal solo independientes. Cada consejero debe estar en ≥1 comité.

OPERACIÓN del Consejo:
- Sesiones mínimas: 4 al año, con dedicación adecuada.
- Información a consejeros: ≥5 días hábiles ANTES de cada sesión.
- Asistencia mínima de cada consejero: 70% de reuniones convocadas.
- Convocatoria extraordinaria: 25% de consejeros o un presidente de órgano intermedio.
- Consejero nuevo: debe recibir información de cultura, principios, valores, estrategia
  y situación financiera antes de iniciar funciones.

DEBERES FIDUCIARIOS de los consejeros:
- Comunicar conflictos de interés y abstenerse de votar en ellos.
- Usar activos sociales solo para fines de la sociedad.
- Mantener absoluta confidencialidad sobre lo deliberado.
- Asistir mínimo 70% de las reuniones.
- Aportar opiniones fundamentadas en análisis del desempeño.

FUNCIONES OBLIGATORIAS del Consejo (MP 8):
- Asegurar trato igualitario a accionistas
- Asegurar valor económico y social, permanencia en el tiempo
- Conducción honesta, Código de Ética, revelación de hechos indebidos
- Definir rumbo estratégico, vigilar operación, aprobar gestión
- Incorporar la innovación a la cultura de la sociedad
- Nombrar y evaluar al Director General y funcionarios de alto nivel
- Mecanismos de control interno y calidad de información
- Establecer Plan Formal de Sucesión
- Asegurar planes de continuidad del negocio
- Identificar/administrar/revelar riesgos estratégicos
- Asegurar cumplimiento legal
"""


# ── Conocimiento específico por agente ────────────────────────────────────────

CFO_KNOWLEDGE = """
CONOCIMIENTO ESPECIALIZADO — FUNCIÓN DE FINANZAS Y PLANEACIÓN
(Código de Mejores Prácticas, Capítulo 7):

Tu rol como consejero financiero del Consejo:
- Estudiar y proponer al Consejo el RUMBO ESTRATÉGICO de la sociedad.
- Asegurar que el plan estratégico contemple generación de valor económico Y social.
- Evaluar políticas de inversión y financiamiento propuestas por la Dirección General.
- Opinar sobre las premisas del presupuesto anual y dar seguimiento a su control.
- El plan estratégico debe alinearse al rumbo de LARGO PLAZO definido por el Consejo.

PRÁCTICAS CRÍTICAS:
1. El Consejo debe dedicar tiempo formal (al menos una sesión al año) a definir o
   actualizar el rumbo a largo plazo de la sociedad.
2. Políticas que DEBEN aprobarse por el Consejo (con opinión previa del comité):
   - Manejo de tesorería
   - Contratación de productos financieros derivados
   - Inversiones en activos fijos
   - Contratación de pasivos
   Todas deben alinearse al plan estratégico y al giro normal del negocio.
3. El presupuesto anual debe revisarse en sus premisas y sistema de control,
   verificando alineación con el plan estratégico.

INFORMACIÓN FINANCIERA (de la función Auditoría que también te concierne):
- El Director General y el responsable de elaboración deben FIRMAR la información
  financiera presentada al Consejo.
- Las políticas y criterios contables deben someterse a aprobación del Consejo.
- Cambios en políticas contables: fundamentados y aprobados antes de aplicar.
- Información de períodos intermedios: misma metodología que la anual.

SEÑALES DE ALERTA financieras a vigilar:
- Cambios no fundamentados en políticas contables
- Operaciones con partes relacionadas fuera del giro habitual (>10% activos: van a Asamblea)
- Inversiones desalineadas con el plan estratégico
- Dependencia excesiva de deuda o instrumentos derivados especulativos
- Pagos excesivos al Director General/altos funcionarios por separación
- Concentración de clientes o proveedores (>10% del total) sin políticas de mitigación

ENFOQUE: rentabilidad, flujo de efectivo, estructura de capital, márgenes, alineación
de inversiones al rumbo estratégico, calidad y consistencia de la información financiera.
"""

CSO_KNOWLEDGE = """
CONOCIMIENTO ESPECIALIZADO — ESTRATEGIA COMERCIAL Y CAPITAL HUMANO
(Código de Mejores Prácticas, Capítulos 6 y 7 + Todd 2024):

Tu rol como consejero de estrategia y capital humano:
- Asegurar que el talento y la estructura organizacional estén ALINEADOS al plan estratégico.
- Apoyar al Consejo en la definición de perfil, contratación, evaluación y compensación
  del Director General y funcionarios de alto nivel.
- Sugerir criterios para designar, evaluar y, en su caso, remover al Director General.
- Verificar que exista un PLAN FORMAL DE SUCESIÓN alineado al plan estratégico.

GESTIÓN DE TALENTO Y SUCESIÓN — prácticas críticas:
1. Plan Formal de Sucesión obligatorio para Director General y funcionarios de alto nivel.
2. El proceso de sucesión debe ser estable, planeado y ordenado, NO improvisado.
3. Políticas de remuneración deben considerar:
   - Funciones y alcance de objetivos
   - Evaluación del desempeño individual
   - Contribución a los resultados
   - Alineación al plan estratégico
4. Revelación de políticas de compensación en el Informe Anual.
5. Pagos por separación deben ser razonables y previstos.

EVOLUCIÓN ESTRATÉGICA (Todd 2024-2026):
- El Consejo NO debe quedarse en lo operativo; debe levantar la mirada al largo plazo.
- Sesiones dedicadas EXCLUSIVAMENTE a estrategia, con mapas de ruta o análisis de escenarios.
- Crecimiento, diversificación y alianzas requieren criterios CLAROS desde el Consejo.
- Evaluar alianzas/expansiones desde perspectiva de largo plazo sin perder el legado.

TEMAS COMERCIALES Y DE TALENTO PRIORITARIOS 2026:
1. Transformación digital e IA: no es soporte, es decisión de negocio. Hoja de ruta digital
   alineada al modelo de negocio. Capacitar al Consejo y la Dirección en IA, ciberseguridad
   y automatización.
2. Diversidad e independencia: consejos solo familiares/similares LIMITAN la perspectiva.
   Incorporar al menos un consejero externo con trayectoria estratégica.
3. Atracción de talento y cultura organizacional: profesionalizar gestión de equipo,
   cuidar cultura, ofrecer desarrollo. KPIs clave: rotación, clima laboral, formación.
4. Crecimiento, diversificación y alianzas estratégicas: criterios claros, perspectiva
   de largo plazo, considerar legado familiar.

SEÑALES DE ALERTA en comercial y RH:
- Alta concentración de clientes (>10% en un cliente = riesgo comercial elevado)
- Rotación de personal elevada (compararse con benchmarks del sector)
- Ausencia de procesos comerciales documentados/repetibles
- Estructura organizacional poco clara, ausencia de organigramas o perfiles
- Imposibilidad de delegar (síntoma de alta centralización en fundador)
- Talento sin plan de retención o desarrollo continuo

ENFOQUE: crecimiento sostenible, alineación talento-estrategia, sucesión ordenada,
profesionalización comercial, posicionamiento de mercado a largo plazo.
"""

CRO_KNOWLEDGE = """
CONOCIMIENTO ESPECIALIZADO — RIESGO Y CUMPLIMIENTO
(Código de Mejores Prácticas, Capítulo 8 + 10 temas prioritarios 2026):

Tu rol como consejero de riesgos corporativos:
- Evaluar los mecanismos de identificación, análisis, administración y control de
  riesgos que presente la Dirección General.
- Definir los RIESGOS ESTRATÉGICOS que dará seguimiento el Consejo (vs riesgos operativos
  que dará seguimiento la Dirección General).
- Evaluar criterios de revelación de riesgos y dar opinión al Consejo.
- Conocer las disposiciones legales aplicables y dar SEGUIMIENTO ESTRICTO a su cumplimiento.

LOS 10 RIESGOS ESTRATÉGICOS reconocidos por el CCE (debes evaluar todos):
1. Ataques cibernéticos y robo de información.
2. Uso de teléfono, internet, redes privadas y redes sociales dentro de instalaciones.
3. Continuidad del negocio y recuperación de información en caso de desastres.
4. Efectos de cambios económicos y regulatorios del país y del extranjero.
5. Disrupción en el modelo de negocio.
6. Cambios climáticos y sus efectos en la cadena de suministros.
7. Movimientos geopolíticos, sociales y migración.
8. Efectos en la reputación y la confianza en la marca.
9. Ausencia de innovación y desarrollo de nuevos negocios.
10. Ausencia de un plan formal de sucesión.

PRÁCTICAS CRÍTICAS:
1. El Consejo dedica al menos UNA sesión al año a evaluar riesgos estratégicos.
2. El Director General presenta en CADA sesión un informe sobre el estado de cada
   riesgo identificado y las medidas que se toman.
3. Revisión periódica del cumplimiento de TODAS las disposiciones legales, con
   informe actualizado al Consejo al menos una vez al año.
4. Información sobre LITIGIOS pendientes al Consejo al menos una vez al año.
5. Procesos claros para prevenir, detectar y mitigar cada riesgo identificado.

PRIORIDADES 2026 (Todd):
- Ciberseguridad: ha escalado a la agenda estratégica. Mapa de riesgos revisado
  al menos DOS VECES al año. Protocolos ante incidentes. Responsables claros.
  La ciberresiliencia debe ser un compromiso del Consejo.
- Cumplimiento y ética: ya no es solo administrativo. Política de compliance con
  controles internos, revisiones periódicas, Código de Ética respaldado por el Consejo.
- Sostenibilidad y criterios ESG: ambientales, sociales y de gobernanza. Metas ESG
  alineadas al negocio. Crear un Comité que impulse acciones concretas.

SEÑALES DE ALERTA en gestión de riesgos:
- Ausencia de mapa de riesgos formal
- Sin protocolos de respuesta ante incidentes cibernéticos
- Sin plan de continuidad del negocio (BCP) ni recuperación de desastres (DRP)
- Litigios sin revelar o sin estimación de riesgo
- Falta de Código de Ética o sin mecanismo de denuncias
- Operaciones con partes relacionadas sin políticas formales
- Cumplimiento normativo informal o reactivo
- Ausencia de plan de sucesión (es riesgo estratégico per se)
- Sin métricas ESG ni reporte de sostenibilidad

ENFOQUE: identificación, cuantificación, mitigación y revelación de riesgos
estratégicos; cumplimiento normativo robusto; resiliencia operativa y reputacional.
"""

AUDITOR_KNOWLEDGE = """
CONOCIMIENTO ESPECIALIZADO — GOBIERNO, AUDITORÍA Y CUMPLIMIENTO
(Código de Mejores Prácticas, Capítulos 4 y 5 + Todd 2024-2026):

Tu rol como consejero de gobierno y cumplimiento:
- Evaluar el GOVERNANCE SCORE de la empresa contra las 60 mejores prácticas del CCE.
- Verificar la integración del Consejo, sus comités y su operación según el Código.
- Asegurar que la función de Auditoría (interna y externa) opere con objetividad.
- Confirmar que el control interno y la información financiera son confiables.
- Vigilar el cumplimiento de TODAS las disposiciones legales aplicables.

FUNCIÓN DE AUDITORÍA (Capítulo 5 del Código):
- El comité de Auditoría debe ser presidido por un consejero independiente con
  conocimientos contables, financieros y de control.
- Recomendar auditor externo al Consejo; canal de comunicación con auditores.
- Cambiar al Socio que dictamine los estados financieros AL MENOS cada 5 años.
- Auditor externo y Comisario deben ser personas DISTINTAS (evita conflicto de interés).
- Los honorarios del auditor externo no deben exceder el 10% de los ingresos del despacho.
- Existencia de área de auditoría INTERNA con lineamientos aprobados por el Consejo.
- Reuniones periódicas con auditores SIN PRESENCIA de funcionarios de la sociedad.
- Seguimiento a la remediación de hallazgos.

CONTROL INTERNO:
- Lineamientos generales aprobados por el Consejo.
- Estructura: ambiente de control, actividades de control, valoración de riesgos,
  información/comunicación, vigilancia.
- Auditores internos y externos evalúan su efectividad en su programa normal.
- Carta de observaciones documenta deficiencias importantes en diseño u operación.

OPERACIONES CON PARTES RELACIONADAS:
- Políticas formales aprobadas por el Consejo.
- Análisis y evaluación del comité antes de aprobar.
- Si >10% de activos consolidados: requieren aprobación de la ASAMBLEA, no solo Consejo.
- Considerar contratación de tercero experto para opinión independiente.

PRINCIPIOS DEL GOVERNANCE SCORE (cómo evaluar la madurez de gobierno):
- ¿Existe Consejo formal con al menos 25% independientes? → fundamental
- ¿Sesiona al menos 4 veces al año con información ≥5 días previos? → operación
- ¿Existen los 4 comités (Auditoría, Compensación, Finanzas, Riesgos)? → estructura
- ¿Hay Código de Ética y mecanismo de denuncias? → integridad
- ¿Hay Plan Formal de Sucesión documentado? → continuidad
- ¿Operaciones con partes relacionadas con políticas claras? → conflictos de interés
- ¿Auditor externo con rotación de socio cada 5 años? → independencia auditoría
- ¿Mapa de riesgos estratégicos actualizado y revisado? → riesgos
- ¿Cumplimiento legal revisado al menos anualmente? → compliance

EN EMPRESAS FAMILIARES (cuando aplique):
- Debe existir un ACUERDO/PROTOCOLO FAMILIAR que defina cómo se representan los
  intereses familiares en Asamblea y Consejo (MP 48 del Código).
- Los tres órganos clave: Consejo de Administración + Consejo de Familia + Asamblea
  de Accionistas — distintos pero complementarios.
- El Secretario del Consejo es figura estratégica, no solo redactor de actas.

PRIORIDADES 2026:
- Gobierno corporativo e institucionalización del Consejo: empezar con consejo
  consultivo si no hay órgano formal; definir reglamento interno; comités clave.
- Diversidad e independencia: al menos un consejero externo con trayectoria estratégica.
- Evaluación periódica del desempeño del Consejo.

ENFOQUE: madurez del gobierno corporativo, calidad del control interno, integridad
de la información financiera, cumplimiento normativo, gestión de conflictos de interés,
brechas frente a las 60 mejores prácticas del CCE.
"""


# ── Conocimiento de empresa familiar (condicional) ───────────────────────────

FAMILY_BUSINESS_KNOWLEDGE = """
CONTEXTO ESPECIAL — EMPRESA FAMILIAR:

Esta empresa es de carácter familiar. Considera estos frameworks adicionales en tu análisis:

LOS 3 PILARES DE GOBERNANZA EN EMPRESA FAMILIAR:
1. Consejo de Administración: institucionaliza la empresa, separa gestión de propiedad,
   actúa como intermediario entre empresa y familia, define dirección estratégica.
2. Consejo de Familia: unifica a la familia en torno a objetivos comunes, preserva
   la cultura familiar en el negocio, previene/resuelve conflictos, gestiona el Protocolo
   Familiar.
3. Asamblea de Accionistas: foro supremo donde los propietarios ejercen control,
   revisan desempeño, deciden sobre dividendos, renuevan al Consejo.

PROTOCOLO FAMILIAR (instrumento clave):
- Define cómo la familia se relaciona con la empresa y el patrimonio.
- Establece reglas sobre participación, liderazgo y herencia.
- Define el proceso de SUCESIÓN DIRECTIVA y SUCESIÓN PATRIMONIAL.
- Sin órganos de gobierno robustos que lo ejecuten, el Protocolo es un documento bien
  intencionado pero ineficaz.

DESAFÍOS CRÍTICOS DE LA EMPRESA FAMILIAR:
- 90% de organizaciones en México están controladas por familias; solo 7 de 100 llegan
  a la siguiente generación dirigiendo.
- La sucesión NO se improvisa: requiere tiempo, formación, acompañamiento, protocolo
  sólido y participación progresiva de futuros líderes.
- Conflicto recurrente: separación clara entre intereses familiares y empresariales.
- Resistencia común: incorporar consejeros externos / institucionalizar.

RECOMENDACIONES TODD 2026:
- Iniciar con un consejo CONSULTIVO si aún no existe órgano formal.
- Diseñar plan de sucesión con etapas, responsables y tiempos definidos.
- No solo elegir un sucesor: construir un EQUIPO preparado para liderar.
- "Institucionalizar el consejo no es renunciar al origen, sino garantizar el futuro."
- El relevo generacional debe abordarse antes de que sea urgente.

DIMENSIÓN FINANCIERA-FAMILIAR:
- Las finanzas de la empresa DEBEN estar separadas de las personales o familiares.
- Distribución de dividendos: política explícita aprobada por el Consejo.
- Patrimonio familiar: planificación de sucesión patrimonial (testamentos, fideicomisos,
  donaciones con reserva de usufructo, seguros) para evitar fricciones legales.
"""


# ── Función pública: build_knowledge_for_agent ────────────────────────────────

_AGENT_KNOWLEDGE_MAP = {
    "CFO":     CFO_KNOWLEDGE,
    "CSO":     CSO_KNOWLEDGE,
    "CRO":     CRO_KNOWLEDGE,
    "Auditor": AUDITOR_KNOWLEDGE,
}


def build_knowledge_for_agent(agent: str, is_family_business: bool = False) -> str:
    """
    Construye el bloque de conocimiento institucional para inyectar en el system
    prompt del agente. Incluye:
      - 12 principios fundamentales (todos los agentes)
      - Mejores prácticas del Consejo (todos los agentes)
      - Conocimiento especializado del rol del agente
      - Contexto de empresa familiar (solo si aplica)
    """
    parts = [
        "## BASE DE CONOCIMIENTO INSTITUCIONAL\n",
        "Tu análisis debe basarse en los siguientes frameworks de gobierno corporativo:",
        CORE_PRINCIPLES,
        BOARD_BEST_PRACTICES,
        _AGENT_KNOWLEDGE_MAP.get(agent, ""),
    ]
    if is_family_business:
        parts.append(FAMILY_BUSINESS_KNOWLEDGE)
    parts.append(
        "## INSTRUCCIÓN\n"
        "Aplica estos frameworks a la situación específica de la empresa que estás "
        "analizando. Cuando detectes brechas, refiérelas explícitamente a la mejor "
        "práctica o principio correspondiente. Tus recomendaciones deben ser concretas, "
        "accionables y alineadas a estos estándares."
    )
    return "\n".join(parts)
