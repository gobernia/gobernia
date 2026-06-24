"""Banco de referencia del diagnóstico (las 7 áreas y sus afirmaciones) + datos esenciales.
Las afirmaciones son una GUÍA opcional: Todd decide cuáles tocar según la conversación.
"""

AREAS = ["estrategia", "comercial", "operativo", "rh", "financiero", "legal", "familiar"]

AREA_BANK = {
    "estrategia": [
        "Cuenta con sistemas que facilitan la administración de información (ERP, MRP, CRM)",
        "Confía en la información de sus sistemas para la toma de decisiones",
        "Tiene una planeación estratégica, misión y visión",
        "Tiene proyecciones anuales de ingreso, costo y gasto",
        "Cuenta con un consejo (consultivo/administración) que evalúa los resultados de la dirección general",
        "Tiene un tablero de indicadores para medir y monitorear el cumplimiento de objetivos",
        "Tiene claridad financiera sobre el uso de utilidades e inversiones de la empresa",
    ],
    "comercial": [
        "Tiene bien identificado su nicho de mercado",
        "Tiene bien identificados a los participantes en la toma de decisión",
        "Conoce y satisface los insights de los tomadores de decisión",
        "Cuenta con una propuesta de valor clara",
        "Tiene pulverizada su venta (no concentrada en pocos clientes)",
        "Cuenta con listas de precios y descuentos claras",
        "Tiene identidad corporativa (marca y logo) clara y reconocida",
        "Realiza estrategias publicitarias o de prospección",
        "Cuenta con un programa de desarrollo comercial (distribuidores, vendedores, etc.)",
        "Tiene pensado diversificar o ampliar su cartera de productos/servicios",
        "Tiene pensado expandir su cobertura geográfica en el corto/mediano plazo",
        "Cuenta con programas para evitar perder o dejar de atender clientes actuales",
        "Cuenta con programas que premian la lealtad de sus clientes",
    ],
    "operativo": [
        "Cuenta con alguna certificación de sus procesos (ISO, NOMs, FDA, etc.)",
        "Tiene mapeados e identificados sus principales procesos",
        "Está libre de cuellos de botella",
        "Tiene inventarios óptimos y bien contabilizados",
        "Considera que los precios de compra a proveedores son los mejores",
        "Cuenta con un programa de desarrollo y evaluación de proveedores",
        "Cuenta con indicadores para medir el desempeño de sus procesos",
        "Considera su sistema de distribución óptimo (entregas a tiempo y completas)",
        "Cuenta con maquinaria, equipo o tecnología para ser más eficiente",
        "Usa al menos el 60% de su capacidad instalada",
    ],
    "rh": [
        "Tiene un proceso formal de reclutamiento y contratación",
        "Tiene una rotación baja o en el promedio de la industria",
        "Tiene sueldos en el promedio o por encima de la industria",
        "Tiene un esquema de compensación ligado al desempeño",
        "Tiene claridad sobre las funciones y responsabilidades de todo su personal",
        "Cuenta con manuales de operación, funciones y perfiles de puestos",
        "Tiene un plan DNC (detección de necesidades de capacitación)",
        "Tiene un plan de desarrollo y crecimiento dentro de la empresa",
    ],
    "financiero": [
        "Revisa el estado de resultados del negocio (P&L)",
        "Lleva el estado de resultado contable en tiempo y forma ante las instituciones correspondientes",
        "Tiene claro y bien valuado su Balance General",
        "Tiene claro el método de costeo directo por producto / unidad de negocio",
        "Tiene presupuesto y control presupuestal (contralor)",
        "Cuenta con un índice de apalancamiento financiero por debajo de 2",
        "Es sujeto de crédito o posee créditos bancarios",
        "Tiene una reserva de capital para poder crecer",
        "Tiene ganancias reales iguales o por encima del promedio de la industria",
    ],
    "legal": [
        "Está libre de requerimientos fiscales y al corriente en el pago de impuestos",
        "Está libre de requerimientos legales, demandas y otros procesos",
        "Tiene protegido su conocimiento (marca registrada, fórmulas, patentes)",
    ],
    "familiar": [
        "Tiene claramente definidas y se cumplen las responsabilidades de los familiares que trabajan en la empresa",
        "Está libre de conflictos familiares que pongan en riesgo la continuidad de la empresa",
        "Tiene claramente separadas las finanzas familiares de las de la empresa",
        "Tiene claro el proceso de sucesión",
    ],
}

# Datos que Todd SÍ debe obtener (la app los consume después).
ESSENTIALS = [
    "Nombre de la empresa (company.name)",
    "Industria / sector (company.industry)",
    "Cuántas personas trabajan en la empresa / tamaño del equipo (company.employees). "
    "Pregúntalo TEMPRANO: define si es una sola persona, un equipo pequeño o más grande.",
    "Ingreso o facturación anual aproximada (company.annual_revenue) — aunque sea un rango. "
    "Sirve para que el plan proponga acciones realistas a su capacidad económica.",
    "Sitio web (company.website)",
    "Competidores que el usuario cree tener (company.competitors)",
    "Si es empresa familiar (company.is_family_business)",
    "Algunos KPIs clave con su valor si los tiene (kpis)",
    "Visión a 3 años (vision.statement)",
]
