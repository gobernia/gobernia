"""Fase externa de Todd: banco PESTEL (factores del entorno) + metas base + prompt externo.
'PESTEL' es término interno; Todd no lo menciona al usuario.
"""
import json

PESTEL_CATS = ["politicos", "economicos", "sociales", "tecnologicos", "ambiental", "legal"]

PESTEL_BANK = {
    "politicos": [
        "Cambios políticos (elecciones, reestructuras de gobierno)",
        "Cambios en poderes o estructura de sindicatos",
        "Afectación de relaciones exteriores por eventos en otros países",
        "Burocracia o corrupción en los procesos de gestión pública",
        "Apoyo al emprendimiento mediante programas sociales",
    ],
    "economicos": [
        "Nuevos impuestos o aranceles",
        "Recesión económica por factores globales o federales",
        "Devaluación del peso vs. dólar u otro tipo de cambio",
        "Transacciones con entidades de recursos de dudosa procedencia",
        "Cambios contables exigidos por dependencias de gobierno",
        "Disputas comerciales que afecten la oferta/demanda",
        "Líneas de crédito que promuevan el crecimiento",
        "Pocas o nulas barreras de entrada para nuevos competidores",
    ],
    "sociales": [
        "Cambios en los hábitos de consumo de la sociedad",
        "Nuevas formas de interacción y comunicación entre personas",
        "Requerimientos de estándares de fiabilidad de productos/servicios",
        "Restricciones en publicidad para difundir contenido",
        "Inseguridad en los traslados de mercancías",
        "Robo de talento capacitado por empresas competidoras",
        "Modas, percepción o tendencias que afecten el consumo",
    ],
    "tecnologicos": [
        "Innovación constante en máquinas o herramientas que optimizan procesos",
        "Desarrollo de nuevos materiales o insumos con mejores beneficios",
        "Actualización de software con más funcionalidades",
        "Obsolescencia de tecnología por avances rápidos",
        "Adquisición de productos/servicios de forma online",
        "Aumento de la delincuencia cibernética",
        "Cambios en los modelos de adquisición de tecnología (leasing) y proveeduría",
    ],
    "ambiental": [
        "Protestas de grupos ambientalistas",
        "Nuevas normas ambientales más estrictas (local o federal)",
        "Aumento de costos de recursos naturales por escasez",
        "Nuevas pandemias o enfermedades",
        "Desastres naturales relacionados con el cambio climático",
    ],
    "legal": [
        "Permisos para la operación de la empresa",
        "Combate a la informalidad de las empresas",
        "Plagio de marca, secretos industriales o invenciones",
        "Corrupción en el otorgamiento de permisos de operación",
        "Demandas por incumplimiento de contratos (servicios, proveedores, empleados)",
        "Cambios en leyes de protección al trabajador",
    ],
}

METAS_BASE = [
    "Conseguir más y mejores clientes",
    "Tener empleados más comprometidos con los objetivos de la empresa",
    "Lograr mayor control de calidad en los procesos",
    "Tener claridad de procesos, funciones, responsabilidades y objetivos",
    "Delegar la dirección, formar un consejo y diversificarse/retirarse",
    "Conocer qué tan bien va respecto al potencial de mercado",
    "Reducir costos y maximizar ganancias/flujos",
]

_CAT_LABEL = {
    "politicos": "Políticos", "economicos": "Económicos", "sociales": "Sociales",
    "tecnologicos": "Tecnológicos", "ambiental": "Ambiental", "legal": "Legal",
}


def build_externo_prompt(state: dict | None, diagnostico_ctx: str) -> str:
    banco = "\n".join(
        f"- {_CAT_LABEL[c]}:\n" + "\n".join(f"    · {item}" for item in PESTEL_BANK[c])
        for c in PESTEL_CATS
    )
    estado_txt = ""
    if state:
        estado_txt = ("\n\nESTADO ACUMULADO ACTUAL (constrúyelo encima, no lo pierdas):\n"
                      + json.dumps(state, ensure_ascii=False))
    return (
        "Eres Todd, el secretario del consejo de Gobernia. Ya entrevistaste a la empresa por dentro "
        "y tienes su diagnóstico. Ahora exploras el ENTORNO EXTERNO: una segunda ronda de preguntas, "
        "cálida y profesional, en español, UNA pregunta a la vez.\n\n"
        "DIAGNÓSTICO DE LA EMPRESA (úsalo para preguntar con foco):\n" + (diagnostico_ctx or "(no disponible)") + "\n\n"
        "Explora los factores del entorno por categoría (políticos, económicos, sociales, tecnológicos, "
        "ambientales, legales) usando el banco de abajo como GUÍA (no obligatorio preguntar todo; salta lo "
        "que no aplique, profundiza lo relevante según el diagnóstico). Clasifica cada factor relevante como "
        "OPORTUNIDAD (juega a favor) o AMENAZA (en contra) en 'state.factores_externos' = "
        "{categoria: [{\"tipo\":\"oportunidad\"|\"amenaza\",\"texto\":\"...\"}]}.\n\n"
        "BANCO DE FACTORES POR CATEGORÍA (guía):\n" + banco + "\n\n"
        "REGLAS:\n"
        "1. Preguntas concretas, una a la vez. Usa 'single_choice' con 'options' cuando aplique "
        "(p. ej. [\"Sí, nos afecta\",\"Más o menos\",\"No\"]); si no, 'text'.\n"
        "2. NO uses tecnicismos como «análisis del entorno» ni nombres de marcos teóricos; habla natural.\n"
        "3. Mantén y DEVUELVE el 'state' completo: marca cada categoría en 'areas_cubiertas' "
        "(usa exactamente: politicos, economicos, sociales, tecnologicos, ambiental, legal) cuando la "
        "exploraste, y acumula 'factores_externos'.\n"
        "4. NUNCA repitas una pregunta ya hecha.\n"
        "5. Pon 'done': true SOLO cuando cubriste las 6 categorías; en ese turno 'message' es un cierre "
        "cálido (avisa que ahora priorizarán sus metas)."
        + estado_txt
    )
