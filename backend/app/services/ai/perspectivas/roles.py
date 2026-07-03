"""Roles de perspectivas + guía de temas por rol (opcional; el agente adapta)."""

ROLES = ["empleado", "directivo", "socio", "cliente", "proveedor"]

ROLE_LABEL = {
    "empleado": "Empleado clave",
    "directivo": "Directivo",
    "socio": "Socio",
    "cliente": "Cliente",
    "proveedor": "Proveedor / aliado",
}

# Roles cuyas respuestas se muestran SIEMPRE agregadas/anónimas (nunca nombre).
ANONYMOUS_ROLES = {"empleado", "cliente"}

# Guía de temas por rol (el agente pregunta SOLO lo que ese rol conoce bien).
ROLE_BANK = {
    "empleado": [
        "Claridad de sus funciones y responsabilidades",
        "Qué tan claros y ágiles son los procesos del día a día",
        "Cuellos de botella o trabas que ve en la operación",
        "Cómo percibe la comunicación y el clima laboral",
        "Qué cambiaría para trabajar mejor",
    ],
    "directivo": [
        "Claridad de la estrategia y las prioridades de la empresa",
        "Fortalezas y debilidades que ve en el negocio",
        "Salud financiera y de crecimiento (a alto nivel)",
        "Riesgos principales que percibe",
        "Qué debería cambiar la dirección",
    ],
    "socio": [
        "Visión de largo plazo y alineación entre socios",
        "Fortalezas y riesgos del negocio",
        "Uso de utilidades e inversiones",
        "Gobierno y toma de decisiones",
    ],
    "cliente": [
        "Qué tan clara y valiosa percibe la propuesta de valor",
        "Por qué compra (o dejaría de comprar)",
        "Calidad del producto/servicio y del trato",
        "Qué mejoraría de su experiencia",
        "Cómo lo compara con otras opciones del mercado",
    ],
    "proveedor": [
        "Confiabilidad de la relación comercial (pagos, comunicación)",
        "Qué tan fácil es trabajar con la empresa",
        "Oportunidades de mejora en la colaboración",
    ],
}
