"""Catálogo por defecto de Temas del Consejo (Bloque B1).
Se siembra al crear un AnnualPlan. every_n_sessions: 1=cada sesión, 2=bimestral,
3=trimestral, 6=semestral, 12=anual."""

DEFAULT_THEMES: list[dict] = [
    # Permanentes — aparecen en TODAS las sesiones
    {"key": "seguimiento_acuerdos",   "label": "Seguimiento de acuerdos", "type": "permanente", "every_n_sessions": 1},
    {"key": "resultados_financieros", "label": "Resultados financieros",  "type": "permanente", "every_n_sessions": 1},
    {"key": "resultados_operativos",  "label": "Resultados operativos",   "type": "permanente", "every_n_sessions": 1},
    {"key": "kpis_estrategicos",      "label": "KPIs estratégicos",       "type": "permanente", "every_n_sessions": 1},
    {"key": "riesgos_criticos",       "label": "Riesgos críticos",        "type": "permanente", "every_n_sessions": 1},
    # Cobertura — rotan por frecuencia
    {"key": "talento_sucesion",           "label": "Talento y sucesión",            "type": "cobertura", "every_n_sessions": 2},
    {"key": "tecnologia_ciberseguridad",  "label": "Tecnología y ciberseguridad",   "type": "cobertura", "every_n_sessions": 2},
    {"key": "auditoria",                  "label": "Auditoría",                     "type": "cobertura", "every_n_sessions": 3},
    {"key": "cumplimiento_normativo",     "label": "Cumplimiento normativo",        "type": "cobertura", "every_n_sessions": 3},
    {"key": "esg",                        "label": "ESG / Sostenibilidad",          "type": "cobertura", "every_n_sessions": 3},
    {"key": "planeacion_estrategica",     "label": "Planeación estratégica",        "type": "cobertura", "every_n_sessions": 6},
    {"key": "evaluacion_dg",              "label": "Evaluación del Director General", "type": "cobertura", "every_n_sessions": 12},
    {"key": "evaluacion_consejo",         "label": "Evaluación del Consejo",        "type": "cobertura", "every_n_sessions": 12},
]
