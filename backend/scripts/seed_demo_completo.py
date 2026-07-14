"""Deja una cuenta LISTA PARA DEMO con TODAS las features nuevas, en un solo comando.

Empresa ficticia: **Keting Media** — agencia de medios y desarrollo digital, 24 empleados,
$4.2M USD de facturación, empresa familiar de 2ª generación. Todos los números (KPIs,
estado de resultados, presentación) son COHERENTES entre sí: es lo que hace creíble la demo
y permite ver si el consejo detecta las contradicciones reales.

Siembra:
  1. OnboardingSession completo (8 etapas, memory_buffer con company/vision/kpis/hallazgos).
  2. DiagnosticoEstrategico "active" (secciones, hallazgos, riesgos, PESTEL, FODA activo).
  3. AnnualPlan "active" con el ROADMAP completo (campos nuevos) en estado "borrador".
  4. CompanyLogo generado con Pillow (cuadrado navy con las iniciales "KM").
  5. BoardSession del periodo, SIN análisis (para darle "Analizar" en vivo).
  6. Board pack: 2 PDFs reales (estado de resultados + presentación estratégica) generados
     con reportlab y subidos a storage, con sus filas Document.

IDEMPOTENTE: empieza borrando TODOS los datos previos del usuario (misma lógica que
scripts/reset_user_data.py) y siembra de cero. Se puede correr N veces.

USO (desde backend/, SOLO con autorización humana — toca la DB):
    venv/bin/python -m scripts.seed_demo_completo correo@ejemplo.com

OJO: usa el DATABASE_URL configurado (apunta a PROD). NO lo corras sin autorización.
"""
import asyncio
import sys
import uuid
from datetime import date, datetime, timezone
from io import BytesIO

from sqlalchemy import text

from app.api.v1.company.service import normalize_logo, upsert_logo
from app.db.session import AsyncSessionLocal
from app.models.annual_plan import AnnualPlan
from app.models.board_session import BoardSession
from app.models.diagnostico_estrategico import DiagnosticoEstrategico
from app.models.document import Document
from app.models.onboarding_session import OnboardingSession
from app.services.documents.storage import generate_storage_key, upload_to_storage
from scripts.reset_user_data import _STEPS as _RESET_STEPS

# ══════════════════════════════════════════════════════════════════════════════
# Números de la empresa — UNA sola fuente de verdad. Los KPIs del onboarding, el
# estado de resultados y la presentación salen de aquí, así que siempre cuadran.
# ══════════════════════════════════════════════════════════════════════════════
EJERCICIO = 2026
ANIO_OBJETIVO = 2029

INGRESOS          = 4_200_000
COSTO_VENTAS      = 2_646_000   # 63.0%
MARGEN_BRUTO      = 1_554_000   # 37.0%
GASTOS_OPERACION  = 1_054_000
EBITDA            =   500_000   # 11.9%
DEP_AMORT         =    92_000
UTIL_OPERACION    =   408_000
GASTOS_FINANCIEROS =   48_000
UTIL_ANTES_IMP    =   360_000
ISR               =   108_000   # 30%
UTILIDAD_NETA     =   252_000   # 6.0% ← margen neto
MARGEN_NETO_PCT   = 6.0

# Concentración: top-3 = 58% de los ingresos.
CLIENTES_TOP = [
    ("Grupo Lasser (retail)",          1_092_000, 26.0),
    ("Banca Prisma (servicios fin.)",    798_000, 19.0),
    ("Aerolínea Mextra",                 546_000, 13.0),
]
RESTO_CLIENTES = ("Otros 17 clientes", 1_764_000, 42.0)
CONCENTRACION_TOP3 = 58.0

ROTACION_PCT       = 31.0
DIAS_CIERRE        = 45
CRECIMIENTO_VENTAS = 4.0
DIAS_COBRO         = 68
RAZON_CORRIENTE    = 1.1
HORAS_FACTURABLES  = 61.0
EMPLEADOS          = 24
GOVERNANCE_SCORE   = 41

NAVY = "#1e3a5f"

# ══════════════════════════════════════════════════════════════════════════════
# 1) memory_buffer del onboarding
# ══════════════════════════════════════════════════════════════════════════════
MEMORY_BUFFER = {
    "company": {
        "name": "Keting Media",
        "industry": "Agencia de medios y desarrollo digital",
        "employees": EMPLEADOS,
        "annual_revenue": "4,200,000 USD",
        "years_operating": 22,
        "website": "https://www.ketingmedia.com",
        "competitors": ["Wizeline", "Neoris", "Globant", "Anagrama", "Kubo Studio"],
        "is_family_business": True,
        "family_generation": "2a",
        "has_family_protocol": False,
        "has_board": False,
        "location": {"city": "Monterrey", "state": "Nuevo León", "country": "México"},
        "branches": 1,
    },
    "vision": {
        "statement": (
            "Que Keting Media sea, en tres años, la agencia de referencia en el norte de México "
            "para marcas que necesitan medios y producto digital en la misma mesa: el doble de "
            "facturación, una cartera de clientes que no dependa de tres cuentas, y un equipo "
            "que retenga a su gente."
        ),
        "exito_consejo": (
            "Que dejemos de depender de que yo apruebe todo. Hoy cada cotización, cada contrato y "
            "cada decisión de diseño pasa por mi escritorio, y eso ya no escala: la empresa crece "
            "hasta donde alcanzan mis horas. Para mí este consejo habrá valido completamente la "
            "pena si dentro de tres años puedo irme tres meses y la empresa siga creciendo sin mí "
            "— y si el día que mi hermana y yo tengamos que decidir la sucesión, sea una junta de "
            "trabajo y no un pleito familiar."
        ),
        "main_goals": [
            "Duplicar la facturación sin sacrificar el margen",
            "Bajar la concentración de clientes",
            "Dejar de ser el cuello de botella de la operación",
        ],
    },
    "governance": {"score": GOVERNANCE_SCORE, "level": "Incipiente"},
    "kpis": {
        "financiero": [
            {"label": "Ingresos anuales", "current_value": INGRESOS, "unit": " USD",
             "benchmark": None, "alert": ""},
            {"label": "Margen neto", "current_value": MARGEN_NETO_PCT, "unit": "%",
             "benchmark": 11, "alert": "Muy por debajo del benchmark de la industria"},
            {"label": "Margen bruto", "current_value": 37.0, "unit": "%", "benchmark": 45,
             "alert": ""},
            {"label": "Días de cierre contable", "current_value": DIAS_CIERRE, "unit": " días",
             "benchmark": 10, "alert": "El dueño decide a ciegas 45 días al mes"},
            {"label": "Razón corriente", "current_value": RAZON_CORRIENTE, "unit": "x",
             "benchmark": 1.8, "alert": ""},
            {"label": "Días de cuentas por cobrar", "current_value": DIAS_COBRO, "unit": " días",
             "benchmark": 45, "alert": "Cobranza lenta: financiamos al cliente"},
        ],
        "comercial": [
            {"label": "Crecimiento de ventas", "current_value": CRECIMIENTO_VENTAS, "unit": "%",
             "benchmark": 15, "alert": "Crecimiento por debajo de la inflación del sector"},
            {"label": "Concentración de clientes (top 3)", "current_value": CONCENTRACION_TOP3,
             "unit": "%", "benchmark": 30, "alert": "Riesgo alto de concentración"},
            {"label": "Clientes activos", "current_value": 20, "unit": "", "benchmark": None,
             "alert": ""},
        ],
        "operativo": [
            {"label": "Horas facturables sobre horas disponibles", "current_value": HORAS_FACTURABLES,
             "unit": "%", "benchmark": 75, "alert": "Capacidad ociosa que se paga igual"},
            {"label": "Proyectos entregados a tiempo", "current_value": 64.0, "unit": "%",
             "benchmark": 90, "alert": ""},
        ],
        "rh": [
            {"label": "Rotación de personal", "current_value": ROTACION_PCT, "unit": "%",
             "benchmark": 15, "alert": "Rotación crítica: se va 1 de cada 3 al año"},
        ],
    },
    "hallazgos": {
        "estrategia": [
            {"nota": "La visión de crecimiento es clara y el dueño la comunica bien al equipo.",
             "clasificacion": "fortaleza"},
            {"nota": "No hay planeación estratégica formal ni tablero de indicadores: se decide "
                     "sobre la marcha y con información de hace mes y medio.",
             "clasificacion": "debilidad"},
            {"nota": "Toda decisión relevante (cotizaciones, contratos, contrataciones) pasa por "
                     "el dueño. Es el cuello de botella declarado de la empresa.",
             "clasificacion": "debilidad"},
            {"nota": "No existe consejo consultivo ni ninguna instancia que evalúe a la dirección.",
             "clasificacion": "debilidad"},
        ],
        "comercial": [
            {"nota": "Reputación técnica sólida y cartera de marcas reconocidas: los clientes "
                     "grandes llegan por recomendación.",
             "clasificacion": "fortaleza"},
            {"nota": f"El {CONCENTRACION_TOP3:.0f}% de la facturación viene de solo 3 cuentas. "
                     "Perder una comprometería la nómina del año.",
             "clasificacion": "debilidad"},
            {"nota": "No hay proceso de prospección: la venta es 100% reactiva, por referidos.",
             "clasificacion": "debilidad"},
            {"nota": "Hay lista de precios, pero se descuenta caso por caso sin política escrita.",
             "clasificacion": "parcial"},
        ],
        "operativo": [
            {"nota": "El equipo creativo y de desarrollo entrega calidad reconocida por los clientes.",
             "clasificacion": "fortaleza"},
            {"nota": "Los procesos no están mapeados ni certificados; cada líder de proyecto opera "
                     "a su manera.",
             "clasificacion": "debilidad"},
            {"nota": f"Solo el {HORAS_FACTURABLES:.0f}% de las horas disponibles se facturan; el "
                     "resto se pierde en retrabajos y juntas.",
             "clasificacion": "debilidad"},
            {"nota": "Se empezó a usar un sistema de gestión de proyectos, pero no todo el equipo "
                     "lo actualiza.",
             "clasificacion": "parcial"},
        ],
        "rh": [
            {"nota": "El núcleo de líderes (5 personas) lleva más de 6 años y es leal a la empresa.",
             "clasificacion": "fortaleza"},
            {"nota": f"Rotación del {ROTACION_PCT:.0f}% anual: se va uno de cada tres. Los juniors "
                     "se van a los 11 meses en promedio.",
             "clasificacion": "debilidad"},
            {"nota": "No hay plan de carrera, ni evaluaciones de desempeño, ni esquema de "
                     "compensación variable.",
             "clasificacion": "debilidad"},
            {"nota": "Los sueldos están en el promedio del mercado local, pero por debajo del "
                     "remoto en dólares, que es contra quien realmente compiten por talento.",
             "clasificacion": "parcial"},
        ],
        "financiero": [
            {"nota": "La empresa es rentable y no tiene deuda bancaria significativa.",
             "clasificacion": "fortaleza"},
            {"nota": f"Margen neto de {MARGEN_NETO_PCT:.0f}%, muy por debajo del ~11% de la "
                     "industria. Se factura mucho y se gana poco.",
             "clasificacion": "debilidad"},
            {"nota": f"El cierre contable tarda {DIAS_CIERRE} días: el dueño decide con números "
                     "de hace mes y medio.",
             "clasificacion": "debilidad"},
            {"nota": "No hay costeo por proyecto: no se sabe qué cuenta gana dinero y cuál lo pierde.",
             "clasificacion": "debilidad"},
            {"nota": "Hay presupuesto anual, pero no control presupuestal ni contralor.",
             "clasificacion": "parcial"},
        ],
        "legal": [
            {"nota": "Al corriente en impuestos y sin litigios abiertos.",
             "clasificacion": "fortaleza"},
            {"nota": "La marca «Keting Media» no está registrada ante el IMPI.",
             "clasificacion": "debilidad"},
            {"nota": "Los contratos con clientes grandes no tienen cláusula de propiedad "
                     "intelectual clara sobre el código y las piezas creativas.",
             "clasificacion": "debilidad"},
        ],
        "familiar": [
            {"nota": "La segunda generación (el dueño y su hermana) ya opera la empresa y hay "
                     "confianza entre ambos.",
             "clasificacion": "fortaleza"},
            {"nota": "No hay protocolo familiar ni proceso de sucesión definido, y el fundador "
                     "sigue interviniendo en decisiones sin rol formal.",
             "clasificacion": "debilidad"},
            {"nota": "Las finanzas familiares y las de la empresa no están del todo separadas "
                     "(gastos personales pasan por la empresa).",
             "clasificacion": "debilidad"},
            {"nota": "Los roles de los dos hermanos están definidos de palabra, no por escrito.",
             "clasificacion": "parcial"},
        ],
    },
    "ai_context": {
        "company_narrative": (
            "Keting Media es una agencia de medios y desarrollo digital de Monterrey, empresa "
            "familiar de segunda generación con 22 años de operación y 24 empleados. Factura "
            "4.2 MDD al año con un margen neto de apenas 6%. Su reputación técnica le trae "
            "clientes grandes por recomendación, pero el 58% de sus ingresos depende de solo 3 "
            "cuentas, la rotación de personal es del 31% y el dueño es el cuello de botella de "
            "toda decisión. Quiere duplicar la facturación en 3 años, dejar de ser indispensable "
            "y ordenar la sucesión familiar antes de que se vuelva un conflicto."
        )
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# 2) Diagnóstico estratégico (shape real: sections + sources + hallazgos + riesgos
#    + factores_externos + foda). Ver app/services/ai/diagnostico_estrategico.py.
# ══════════════════════════════════════════════════════════════════════════════
_SECTIONS = {
    "resumen_ejecutivo": (
        "Keting Media es una empresa técnicamente sólida y financieramente frágil. Factura 4.2 "
        "millones de dólares con una reputación que le trae clientes grandes sin salir a "
        "buscarlos, pero convierte esa facturación en apenas 252 mil dólares de utilidad: un "
        "margen neto del 6%, frente al 11% típico de agencias comparables. El problema no es la "
        "demanda, es la conversión: se vende bien y se opera caro.\n\n"
        "Tres hechos definen el riesgo del negocio hoy. Primero, la concentración: el 58% de los "
        "ingresos vive en tres cuentas, y perder cualquiera de ellas borraría la utilidad del año "
        "completo. Segundo, la fuga de talento: una rotación del 31% en un negocio cuyo único "
        "activo son las personas significa reconstruir un tercio de la capacidad cada año. "
        "Tercero, la dependencia del dueño: todas las decisiones pasan por él, lo que fija un "
        "techo de crecimiento en sus horas disponibles.\n\n"
        "La empresa tiene la marca, el equipo y el mercado para duplicar tamaño. Lo que no tiene "
        "es la estructura: no hay costeo por proyecto, no hay tablero, el cierre contable tarda 45 "
        "días y no existe ninguna instancia que le exija cuentas a la dirección. Ordenar eso es la "
        "condición para crecer, no un lujo posterior."
    ),
    "presencia_digital": (
        "El sitio de Keting Media funciona como portafolio, no como canal de adquisición: muestra "
        "trabajo, no captura prospectos. No hay formularios de contacto calificados, ni contenido "
        "que posicione a la agencia en las búsquedas de sus compradores, ni casos de estudio con "
        "resultados de negocio (solo piezas visuales).\n\n"
        "Para una agencia que vende servicios digitales, esa ausencia es una contradicción visible "
        "para el cliente: la casa del herrero. Los competidores regionales publican casos con "
        "métricas, hacen contenido técnico y aparecen en las búsquedas de «agencia de medios "
        "Monterrey»; Keting aparece solo si ya la conocen por nombre.\n\n"
        "En redes profesionales el equipo tiene presencia individual fuerte, pero la marca "
        "corporativa casi no publica. La reputación existe, pero vive en la cabeza de un puñado de "
        "clientes satisfechos, no en un activo digital que trabaje mientras el dueño duerme."
    ),
    "competencia": (
        "El dueño identifica como competidores a Wizeline, Neoris, Globant, Anagrama y Kubo "
        "Studio. La lista mezcla dos ligas distintas y eso importa. Wizeline, Neoris y Globant son "
        "consultoras de software de escala internacional: compiten por el presupuesto de "
        "tecnología de corporativos, con cientos o miles de ingenieros. Keting no compite contra "
        "ellas por proyecto — compite contra ellas por TALENTO, y ahí sí las enfrenta todos los "
        "días, porque pagan en dólares y ofrecen carrera. Esa es la competencia real detrás del "
        "31% de rotación.\n\n"
        "Anagrama y Kubo Studio sí son competencia comercial directa: estudios regionales con "
        "propuesta creativa fuerte y estructura ligera. Contra ellos, la ventaja de Keting es "
        "poder ofrecer medios y desarrollo en la misma mesa; la desventaja es que Keting carga con "
        "una estructura más pesada y un margen más delgado.\n\n"
        "Falta en la lista del dueño un competidor que ya le está quitando trabajo sin que lo "
        "vea: los equipos internos de marketing y producto de sus propios clientes grandes. "
        "Cuando una cuenta como Banca Prisma internaliza su equipo digital, no cambia de agencia: "
        "deja de necesitarla. Ese es el escenario que la concentración del 58% convierte en "
        "existencial."
    ),
    "tendencias_mercado": (
        "El mercado de servicios digitales en México sigue creciendo, pero se está partiendo en "
        "dos: por arriba, consultoras que venden transformación con equipos grandes; por abajo, "
        "estudios boutique y freelancers con costos mínimos y herramientas de IA. Las agencias de "
        "tamaño medio — exactamente donde está Keting — son las que sufren la compresión de "
        "márgenes, porque tienen la estructura de las grandes y los precios de las chicas.\n\n"
        "La adopción de IA generativa en producción creativa y desarrollo está bajando el costo "
        "por pieza y por línea de código. Para quien la adopta primero, es una expansión de margen; "
        "para quien tarda, es una guerra de precios que no puede ganar. En 24 meses el cliente va "
        "a esperar que la agencia entregue más rápido y más barato, y va a preguntar por qué.\n\n"
        "Del lado de la demanda, los clientes grandes cada vez compran menos «campañas» y más "
        "«producto y medición»: quieren atribución, dashboards, resultados de negocio. Keting tiene "
        "la capacidad técnica para vender eso, pero no lo empaqueta ni lo cobra como tal — hoy lo "
        "regala dentro de proyectos cotizados como creativos."
    ),
    "contexto_economico": (
        "La empresa factura en dólares y paga nómina en pesos, lo que en un peso apreciado "
        "comprime el margen sin que nadie haya tomado una mala decisión. Con un margen neto de 6%, "
        "un movimiento cambiario adverso de un dígito medio se come la utilidad del año. Hoy no "
        "hay ninguna cobertura ni política cambiaria escrita.\n\n"
        "El costo del talento técnico en Monterrey sigue subiendo por encima de la inflación, "
        "empujado por las consultoras internacionales y por el trabajo remoto en dólares. La "
        "presión salarial es estructural, no coyuntural: no se resuelve con un aumento, se "
        "resuelve con carrera, propósito y compensación variable ligada a resultados.\n\n"
        "En lo regulatorio, la exposición más clara es la propiedad intelectual: contratos sin "
        "cláusula clara sobre el código y las piezas, y la marca sin registrar ante el IMPI. Es "
        "barato de arreglar hoy y caro de arreglar el día que un cliente grande o un tercero lo "
        "dispute."
    ),
    "conclusiones": (
        "La lectura del consejo es que Keting Media no tiene un problema de mercado: tiene un "
        "problema de estructura. Vende bien, entrega bien y cobra tarde; gana poco y no sabe con "
        "precisión en qué proyectos lo pierde. Las tres prioridades, en este orden, son:\n\n"
        "1. Ver los números a tiempo. Cerrar el mes en 10 días y tener costeo por proyecto. Sin "
        "esto, cualquier otra decisión es una apuesta. Es lo más barato y lo más urgente.\n\n"
        "2. Romper la concentración. Un proceso de prospección real, con meta y responsable, para "
        "bajar el top-3 del 58% a un rango manejable. Mientras tres clientes puedan hundir el año, "
        "la empresa no es dueña de su estrategia: la negocia cada renovación.\n\n"
        "3. Sacar al dueño del camino crítico. Delegación formal con montos, un comité de dirección "
        "que decida sin él y un plan de carrera que frene la rotación. La definición de éxito del "
        "dueño — poder irse tres meses y que la empresa siga creciendo — no es una aspiración "
        "emocional: es un requisito para que el negocio valga algo el día que se venda o se herede.\n\n"
        "El orden importa: primero se mide, después se ordena, y solo entonces se expande. Crecer "
        "sobre esta estructura duplicaría los ingresos y los problemas al mismo tiempo."
    ),
}

_SECTION_TITLES = {
    "resumen_ejecutivo": "Resumen ejecutivo",
    "presencia_digital": "Presencia digital",
    "competencia": "Competencia: percibida vs. real",
    "tendencias_mercado": "Tendencias de mercado",
    "contexto_economico": "Contexto económico y regulatorio",
    "conclusiones": "Conclusiones y recomendaciones",
}

FUENTES = [
    {"title": "Keting Media — Sitio oficial", "url": "https://www.ketingmedia.com"},
    {"title": "AMITI — Panorama de la industria de TI en México", "url": "https://amiti.org.mx/"},
    {"title": "INEGI — Encuesta Nacional de Ocupación y Empleo (Nuevo León)",
     "url": "https://www.inegi.org.mx/programas/enoe/15ymas/"},
    {"title": "Banxico — Tipo de cambio y expectativas",
     "url": "https://www.banxico.org.mx/tipcamb/main.do"},
    {"title": "IMPI — Registro de marcas", "url": "https://www.gob.mx/impi"},
    {"title": "Wizeline — Careers (benchmark de compensación técnica)",
     "url": "https://www.wizeline.com/careers/"},
    {"title": "Anagrama — Portafolio", "url": "https://anagrama.com/"},
]


def _fortalezas_debilidades() -> dict:
    """Los hallazgos de Todd, en el shape normalizado que persiste el diagnóstico:
    {area: [{tipo, texto}]} (ver _normalize_hallazgos en diagnostico_estrategico.py)."""
    out: dict[str, list[dict]] = {}
    for area, items in MEMORY_BUFFER["hallazgos"].items():
        out[area] = [{"tipo": h["clasificacion"], "texto": h["nota"]} for h in items]
    return out


RIESGOS = [
    {"riesgo": f"Perder cualquiera de las 3 cuentas principales ({CONCENTRACION_TOP3:.0f}% de los "
               "ingresos) borraría la utilidad del año y comprometería la nómina.",
     "severidad": "alta"},
    {"riesgo": f"Con un margen neto de {MARGEN_NETO_PCT:.0f}%, cualquier proyecto mal costeado o un "
               "movimiento cambiario adverso convierte el año en pérdida.",
     "severidad": "alta"},
    {"riesgo": f"La rotación del {ROTACION_PCT:.0f}% destruye conocimiento del cliente y obliga a "
               "reconstruir un tercio de la capacidad operativa cada año.",
     "severidad": "alta"},
    {"riesgo": "La empresa se detiene si el dueño se detiene: no hay delegación formal ni segundo "
               "nivel con autoridad de decisión.",
     "severidad": "alta"},
    {"riesgo": f"Cerrar el mes en {DIAS_CIERRE} días y sin costeo por proyecto significa decidir "
               "con información vieja y no saber qué cuenta gana o pierde dinero.",
     "severidad": "media"},
    {"riesgo": "Sin protocolo familiar ni proceso de sucesión, un desacuerdo entre los hermanos "
               "escalaría a conflicto societario.",
     "severidad": "media"},
    {"riesgo": "La marca sin registrar y los contratos sin cláusula de propiedad intelectual "
               "exponen el activo principal de la empresa.",
     "severidad": "baja"},
]

FACTORES_EXTERNOS = {
    "politicos": [
        {"tipo": "oportunidad",
         "texto": "El nearshoring sigue atrayendo corporativos y plantas al norte del país, y todos "
                  "llegan necesitando marca, medios y producto digital local."},
        {"tipo": "amenaza",
         "texto": "La incertidumbre en el gasto público y en programas de apoyo a PyMEs hace poco "
                  "confiable cualquier plan que dependa de fondeo o incentivos gubernamentales."},
    ],
    "economicos": [
        {"tipo": "amenaza",
         "texto": "Facturar en dólares y pagar nómina en pesos: con un peso fuerte, el margen se "
                  "comprime sin que nadie tome una mala decisión."},
        {"tipo": "amenaza",
         "texto": "El costo del talento técnico sube por encima de la inflación, empujado por las "
                  "consultoras internacionales y el trabajo remoto en dólares."},
        {"tipo": "oportunidad",
         "texto": "Los presupuestos de marketing digital de las empresas medianas siguen creciendo "
                  "a doble dígito y se mueven de campañas a producto y medición."},
    ],
    "sociales": [
        {"tipo": "amenaza",
         "texto": "Los perfiles junior ya no quieren oficina ni jerarquía: sin plan de carrera "
                  "visible, se van al primer ofrecimiento remoto."},
        {"tipo": "oportunidad",
         "texto": "Las marcas buscan agencias con equipo propio y cercanía cultural, no solo el "
                  "precio más bajo de un proveedor offshore."},
    ],
    "tecnologicos": [
        {"tipo": "oportunidad",
         "texto": "La IA generativa puede bajar el costo por pieza creativa y por línea de código: "
                  "para el que la adopte primero, es margen; para el que tarde, es guerra de precios."},
        {"tipo": "amenaza",
         "texto": "Las herramientas no-code y de IA permiten que un cliente mediano resuelva "
                  "internamente lo que hoy contrata: la parte baja del catálogo se comoditiza."},
    ],
    "ambiental": [
        {"tipo": "oportunidad",
         "texto": "Los clientes corporativos empiezan a exigir a sus proveedores criterios ESG "
                  "básicos; cumplirlos es un diferenciador barato frente a estudios pequeños."},
    ],
    "legal": [
        {"tipo": "amenaza",
         "texto": "El endurecimiento de las reglas de datos personales y publicidad digital obliga "
                  "a rehacer procesos de medición y consentimiento en las campañas de los clientes."},
        {"tipo": "amenaza",
         "texto": "Sin la marca registrada y sin cláusulas claras de propiedad intelectual, el "
                  "activo principal de la empresa está legalmente expuesto."},
    ],
}

METAS_ORDEN = [
    "Duplicar la facturación en 3 años sin sacrificar el margen",
    "Bajar la concentración del top-3 de clientes",
    "Que la empresa opere sin depender de la aprobación del dueño",
    "Frenar la rotación de personal y retener al talento clave",
    "Ver los números a tiempo: cierre mensual rápido y costeo por proyecto",
    "Ordenar la sucesión y la relación familia-empresa",
]

FODA = {
    "fortalezas": [
        "Reputación técnica que atrae clientes grandes sin salir a buscarlos: la marca vende sola.",
        "Único jugador regional que ofrece medios y desarrollo de producto en la misma mesa.",
        "Núcleo de líderes leal y con más de 6 años de casa: el conocimiento del cliente vive ahí.",
        "Rentable y sin deuda bancaria: hay margen de maniobra para invertir sin pedir prestado.",
    ],
    "oportunidades": [
        "El nearshoring trae corporativos nuevos al norte que necesitan exactamente lo que Keting "
        "sabe hacer.",
        "Los clientes están migrando de comprar campañas a comprar producto y medición: Keting ya "
        "puede entregarlo, solo falta empaquetarlo y cobrarlo.",
        "La IA generativa permite expandir margen antes que la competencia lo haga bajar precios.",
        "Los presupuestos digitales de empresas medianas crecen a doble dígito: hay demanda "
        "diversificable disponible.",
    ],
    "debilidades": [
        f"El {CONCENTRACION_TOP3:.0f}% de los ingresos depende de 3 cuentas: la estrategia se "
        "negocia en cada renovación.",
        f"Margen neto de {MARGEN_NETO_PCT:.0f}% contra ~11% de la industria: se factura mucho y se "
        "gana poco.",
        f"Rotación del {ROTACION_PCT:.0f}%: se reconstruye un tercio de la capacidad cada año.",
        "El dueño es el cuello de botella de toda decisión: el crecimiento tiene el techo de sus horas.",
        f"Cierre contable en {DIAS_CIERRE} días y sin costeo por proyecto: se decide a ciegas.",
    ],
    "amenazas": [
        "Que un cliente grande internalice su equipo digital: no cambia de agencia, deja de "
        "necesitarla.",
        "Las consultoras internacionales pagan en dólares y se llevan al talento técnico.",
        "La compresión de márgenes que aplasta a las agencias medianas entre consultoras grandes y "
        "estudios boutique.",
        "Exposición cambiaria sin cobertura: un movimiento adverso se come la utilidad del año.",
    ],
    "sintesis": (
        "La posición de Keting Media es la de una empresa con activos de crecimiento y estructura "
        "de supervivencia. Sus fortalezas —marca, oferta integrada, núcleo leal— la habilitan para "
        "capturar las oportunidades del nearshoring y de la migración hacia producto y medición; "
        "nada en el mercado le impide duplicar tamaño. El cruce peligroso está del otro lado: la "
        "concentración en tres cuentas y el margen de 6% multiplican el efecto de cualquier "
        "amenaza externa, y la rotación del 31% la deja indefensa justo frente a la amenaza que "
        "más la golpea, que es la fuga de talento hacia las consultoras internacionales. Es una "
        "empresa que puede ganar el mercado y perder la empresa al mismo tiempo: la debilidad "
        "interna, no la competencia, es lo que hoy decide su futuro."
    ),
    "metas_priorizadas": METAS_ORDEN,
}


def build_diagnostico_content() -> dict:
    return {
        "sections": [
            {"key": k, "title": _SECTION_TITLES[k], "body": _SECTIONS[k]}
            for k in ("resumen_ejecutivo", "presencia_digital", "competencia",
                      "tendencias_mercado", "contexto_economico", "conclusiones")
        ],
        "sources": FUENTES,
        "fortalezas_debilidades": _fortalezas_debilidades(),
        "riesgos": RIESGOS,
        "factores_externos": FACTORES_EXTERNOS,
        "metas_orden": METAS_ORDEN,
        "foda": FODA,
        "foda_status": "active",
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3) Roadmap estratégico (campos NUEVOS del template). Invariante: `target` de las
#    metas y `meta` de los KPIs SIEMPRE vacíos — el número lo pone el dueño.
# ══════════════════════════════════════════════════════════════════════════════
ROADMAP = {
    "anio_objetivo": ANIO_OBJETIVO,
    "vision": (
        "En 2029 Keting Media es la agencia de referencia del norte de México para marcas que "
        "necesitan medios y producto digital en la misma mesa: el doble de facturación, una cartera "
        "que ya no depende de tres cuentas, y una empresa que crece cuando el dueño no está."
    ),
    "mision": (
        "Convertir la inversión de marketing y tecnología de nuestros clientes en resultados de "
        "negocio medibles, con un equipo propio que entiende su industria y se queda a largo plazo."
    ),
    "propuesta_valor": (
        "Medios y producto digital bajo un mismo techo, con medición de negocio de punta a punta: "
        "el cliente deja de coordinar tres proveedores y empieza a ver una sola cuenta de "
        "resultados."
    ),
    "objetivos_estrategicos": [
        "Duplicar la facturación a 2029 elevando el margen neto, no sacrificándolo.",
        "Reducir la concentración del top-3 de clientes hasta que ninguna cuenta pueda hundir el año.",
        "Construir una dirección que decida sin el dueño: delegación formal, comité y consejo.",
        "Retener al talento clave con carrera, evaluación y compensación ligada a resultados.",
        "Ver los números a tiempo: cierre mensual rápido, costeo por proyecto y tablero vivo.",
    ],
    "key_enablers": [
        "Talento: plan de carrera, evaluación de desempeño y compensación variable.",
        "Tecnología: IA generativa aplicada a producción creativa y desarrollo.",
        "Capital: reserva de utilidades para financiar la expansión sin deuda.",
        "Gobernanza: consejo consultivo con sesiones trimestrales y rendición de cuentas.",
        "Procesos: costeo por proyecto y cierre contable en 10 días.",
    ],
    "temas_por_anio": {
        "anio1": "Ordenar la casa",
        "anio2": "Expandir el negocio",
        "anio3": "Consolidar el liderazgo",
    },
    "conclusion_diagnostico": (
        "Keting Media no tiene un problema de mercado, tiene un problema de estructura: vende bien, "
        "entrega bien y gana poco, sin saber con precisión en qué proyectos pierde. Primero se mide, "
        "después se ordena, y solo entonces se expande."
    ),
    "conclusion_entorno": (
        "El entorno regala demanda y castiga la estructura: el nearshoring y los presupuestos "
        "digitales abren el mercado, mientras la guerra por el talento y la compresión de márgenes "
        "aplastan justo a las agencias medianas. Adoptar IA y retener al equipo no es innovación: "
        "es la condición para seguir compitiendo."
    ),
    "metas_3anios": [
        {"meta": "Duplicar la facturación anual", "kpi": "Ingresos anuales",
         "valor_actual": "4.2M USD", "target": ""},
        {"meta": "Llevar el margen neto al nivel de la industria", "kpi": "Margen neto",
         "valor_actual": f"{MARGEN_NETO_PCT:.0f}%", "target": ""},
        {"meta": "Diversificar la cartera de clientes",
         "kpi": "Concentración de clientes (top 3)",
         "valor_actual": f"{CONCENTRACION_TOP3:.0f}%", "target": ""},
        {"meta": "Retener al talento", "kpi": "Rotación de personal",
         "valor_actual": f"{ROTACION_PCT:.0f}%", "target": ""},
        {"meta": "Decidir con números frescos", "kpi": "Días de cierre contable",
         "valor_actual": f"{DIAS_CIERRE} días", "target": ""},
        {"meta": "Aprovechar la capacidad instalada",
         "kpi": "Horas facturables sobre horas disponibles",
         "valor_actual": f"{HORAS_FACTURABLES:.0f}%", "target": ""},
    ],
    "resumen_foda": FODA["sintesis"],
    "resumen_entorno": (
        "Demanda al alza por el nearshoring y por la migración del cliente hacia producto y "
        "medición; presión estructural sobre el margen por el costo del talento, la exposición "
        "cambiaria y la comoditización que trae la IA. El mercado premia a quien adopte tecnología "
        "y retenga equipo, y castiga a la agencia mediana que se quede en el punto medio."
    ),
    "pilares": [
        {
            "nombre": "Rentabilidad y control",
            "descripcion": "Ver los números a tiempo y saber qué proyecto gana dinero, para dejar "
                           "de decidir a ciegas y proteger el margen.",
            "objetivo": "Elevar el margen neto al nivel de la industria sin perder volumen, con "
                        "información financiera confiable y oportuna.",
            "estrategias": [
                "Implantar costeo por proyecto: cada cuenta con su propia cuenta de resultados.",
                "Acelerar el cierre contable a 10 días y montar un tablero mensual de indicadores.",
                "Política de precios y descuentos escrita, con piso de margen por tipo de proyecto.",
            ],
            "kpis": [
                {"label": "Margen neto", "actual": f"{MARGEN_NETO_PCT:.0f}%", "meta": ""},
                {"label": "Días de cierre contable", "actual": f"{DIAS_CIERRE} días", "meta": ""},
                {"label": "Días de cuentas por cobrar", "actual": f"{DIAS_COBRO} días", "meta": ""},
            ],
            "resultados_esperados": [
                {"titulo": "↑ Margen neto",
                 "descripcion": "Se deja de cotizar por intuición: cada proyecto entra con piso de "
                                "margen conocido."},
                {"titulo": "↓ Días de cierre",
                 "descripcion": "El dueño decide con números del mes pasado, no de hace mes y medio."},
                {"titulo": "↓ Fuga de rentabilidad",
                 "descripcion": "Los proyectos que pierden dinero se identifican y se corrigen o se "
                                "sueltan."},
            ],
            "fases": {
                "anio1": {"titulo": "Instrumentar y medir"},
                "anio2": {"titulo": "Optimizar el margen"},
                "anio3": {"titulo": "Rentabilidad predecible"},
            },
            "milestones": {
                "anio1": [
                    "Implantar costeo por proyecto en las 3 cuentas principales",
                    "Cerrar el mes contable en 10 días",
                    "Publicar la política de precios y descuentos",
                ],
                "anio2": [
                    "Costeo por proyecto en el 100% de la cartera",
                    "Control presupuestal mensual con responsable por área",
                    "Reducir las cuentas por cobrar a 45 días",
                ],
                "anio3": [
                    "Margen neto en el rango de la industria de forma sostenida",
                    "Reserva de capital equivalente a 3 meses de nómina",
                ],
            },
        },
        {
            "nombre": "Diversificación comercial",
            "descripcion": "Romper la dependencia de tres cuentas con una máquina de prospección "
                           "que hoy no existe: la venta es 100% reactiva.",
            "objetivo": "Bajar la concentración del top-3 hasta que ninguna cuenta pueda comprometer "
                        "el año, creciendo en clientes nuevos.",
            "estrategias": [
                "Proceso de prospección con meta, responsable y pipeline visible.",
                "Empaquetar y cobrar la oferta de «producto + medición» que hoy se regala.",
                "Abrir un segundo segmento (manufactura/nearshoring) fuera del retail y la banca.",
            ],
            "kpis": [
                {"label": "Concentración de clientes (top 3)",
                 "actual": f"{CONCENTRACION_TOP3:.0f}%", "meta": ""},
                {"label": "Crecimiento de ventas", "actual": f"{CRECIMIENTO_VENTAS:.0f}%", "meta": ""},
                {"label": "Clientes activos", "actual": "20", "meta": ""},
            ],
            "resultados_esperados": [
                {"titulo": "↓ Concentración top-3",
                 "descripcion": "Perder una cuenta grande deja de ser un evento existencial."},
                {"titulo": "↑ Clientes nuevos",
                 "descripcion": "La venta deja de depender del referido y se vuelve un proceso "
                                "repetible."},
                {"titulo": "↑ Ticket promedio",
                 "descripcion": "La medición y el producto se cobran; dejan de ser un regalo dentro "
                                "del proyecto creativo."},
            ],
            "fases": {
                "anio1": {"titulo": "Construir el pipeline"},
                "anio2": {"titulo": "Abrir segmentos"},
                "anio3": {"titulo": "Cartera equilibrada"},
            },
            "milestones": {
                "anio1": [
                    "Nombrar responsable comercial y montar el pipeline en CRM",
                    "Cerrar 4 clientes nuevos fuera del top-3",
                    "Lanzar el paquete comercial de «producto + medición»",
                ],
                "anio2": [
                    "Entrar al segmento de manufactura/nearshoring con 2 cuentas ancla",
                    "Bajar la concentración del top-3 por debajo del 45%",
                    "Duplicar el pipeline calificado respecto al año 1",
                ],
                "anio3": [
                    "Ninguna cuenta individual por encima del 15% de los ingresos",
                    "Presencia comercial en una segunda plaza (CDMX o Guadalajara)",
                ],
            },
        },
        {
            "nombre": "Talento y cultura",
            "descripcion": "Frenar la fuga: en un negocio de personas, una rotación del 31% es "
                           "reconstruir un tercio de la empresa cada año.",
            "objetivo": "Retener al talento clave con carrera, evaluación y compensación ligada a "
                        "resultados, para competir contra las consultoras que pagan en dólares.",
            "estrategias": [
                "Plan de carrera con niveles, evaluación de desempeño semestral y rutas de ascenso.",
                "Esquema de compensación variable ligado al margen del proyecto.",
                "Programa de capacitación (DNC) con foco en IA aplicada a creatividad y desarrollo.",
            ],
            "kpis": [
                {"label": "Rotación de personal", "actual": f"{ROTACION_PCT:.0f}%", "meta": ""},
                {"label": "Horas facturables sobre horas disponibles",
                 "actual": f"{HORAS_FACTURABLES:.0f}%", "meta": ""},
                {"label": "Permanencia promedio de los juniors", "actual": "11 meses", "meta": ""},
            ],
            "resultados_esperados": [
                {"titulo": "↓ Rotación",
                 "descripcion": "El conocimiento del cliente deja de irse por la puerta cada año."},
                {"titulo": "↑ Horas facturables",
                 "descripcion": "Menos retrabajo y menos curva de aprendizaje: la misma nómina "
                                "produce más."},
                {"titulo": "↑ Segundo nivel",
                 "descripcion": "Aparecen líderes con autoridad real, no solo con título."},
            ],
            "fases": {
                "anio1": {"titulo": "Frenar la fuga"},
                "anio2": {"titulo": "Desarrollar líderes"},
                "anio3": {"titulo": "Empleador de referencia"},
            },
            "milestones": {
                "anio1": [
                    "Publicar el plan de carrera y los niveles de puesto",
                    "Primera evaluación de desempeño formal a todo el equipo",
                    "Lanzar la compensación variable ligada al margen del proyecto",
                ],
                "anio2": [
                    "Programa de capacitación en IA aplicada para todo el equipo de producción",
                    "Rotación por debajo del 20%",
                    "Cada área con un segundo al mando identificado y en formación",
                ],
                "anio3": [
                    "Rotación en el promedio de la industria",
                    "Los líderes de área contratan y evalúan a su equipo sin el dueño",
                ],
            },
        },
        {
            "nombre": "Gobierno y sucesión",
            "descripcion": "Sacar al dueño del camino crítico y ordenar la relación familia-empresa "
                           "antes de que la sucesión se vuelva un conflicto.",
            "objetivo": "Que la empresa opere y crezca sin depender de la aprobación del dueño, con "
                        "un consejo que le exija cuentas a la dirección.",
            "estrategias": [
                "Delegación formal por montos y comité de dirección semanal que decide sin el dueño.",
                "Instalar el consejo consultivo con sesiones trimestrales e indicadores.",
                "Protocolo familiar: roles, sucesión y separación de finanzas familia-empresa.",
            ],
            "kpis": [
                {"label": "Governance score", "actual": f"{GOVERNANCE_SCORE}/100", "meta": ""},
                {"label": "Decisiones que requieren firma del dueño", "actual": "Todas", "meta": ""},
                {"label": "Sesiones de consejo al año", "actual": "0", "meta": ""},
            ],
            "resultados_esperados": [
                {"titulo": "↑ Autonomía de la dirección",
                 "descripcion": "El techo de crecimiento deja de ser las horas del dueño."},
                {"titulo": "↑ Governance score",
                 "descripcion": "La empresa se vuelve sujeto de crédito y candidata a inversión."},
                {"titulo": "↓ Riesgo de conflicto familiar",
                 "descripcion": "La sucesión se convierte en una junta de trabajo, no en un pleito."},
            ],
            "fases": {
                "anio1": {"titulo": "Instalar el gobierno"},
                "anio2": {"titulo": "Delegar de verdad"},
                "anio3": {"titulo": "Sucesión ordenada"},
            },
            "milestones": {
                "anio1": [
                    "Instalar el consejo consultivo y sesionar trimestralmente",
                    "Política de delegación por montos firmada y en operación",
                    "Comité de dirección semanal con minuta y acuerdos",
                ],
                "anio2": [
                    "Protocolo familiar firmado por la familia",
                    "Separar por completo las finanzas familiares de las de la empresa",
                    "El dueño se ausenta un mes sin que se detenga ninguna decisión",
                ],
                "anio3": [
                    "Plan de sucesión definido y comunicado",
                    "El dueño puede ausentarse tres meses y la empresa sigue creciendo",
                ],
            },
        },
        {
            "nombre": "Innovación y eficiencia",
            "descripcion": "Adoptar IA en producción antes de que la competencia la use para bajar "
                           "precios: hoy es margen, mañana es guerra de precios.",
            "objetivo": "Bajar el costo por entrega y acelerar el time-to-market con IA aplicada, "
                        "convirtiendo la eficiencia en margen y no en descuento.",
            "estrategias": [
                "Integrar IA generativa en el flujo creativo y de desarrollo, con estándares de calidad.",
                "Mapear y estandarizar los procesos de entrega para eliminar el retrabajo.",
                "Construir la oferta de medición y atribución como producto propio, no como extra.",
            ],
            "kpis": [
                {"label": "Proyectos entregados a tiempo", "actual": "64%", "meta": ""},
                {"label": "Margen bruto", "actual": "37%", "meta": ""},
                {"label": "Horas de retrabajo por proyecto", "actual": "No se mide", "meta": ""},
            ],
            "resultados_esperados": [
                {"titulo": "↑ Margen bruto",
                 "descripcion": "La misma entrega cuesta menos horas, y esas horas se facturan a "
                                "otro cliente."},
                {"titulo": "↑ Entregas a tiempo",
                 "descripcion": "Procesos estandarizados: la calidad deja de depender de quién lleve "
                                "el proyecto."},
                {"titulo": "↑ Oferta diferenciada",
                 "descripcion": "La medición se vuelve un producto que se cobra y que nadie más "
                                "ofrece igual en la plaza."},
            ],
            "fases": {
                "anio1": {"titulo": "Adoptar y estandarizar"},
                "anio2": {"titulo": "Escalar la eficiencia"},
                "anio3": {"titulo": "Ventaja competitiva"},
            },
            "milestones": {
                "anio1": [
                    "Mapear los 5 procesos de entrega clave",
                    "Piloto de IA generativa en producción creativa y en desarrollo",
                ],
                "anio2": [
                    "IA integrada al flujo estándar de todos los proyectos",
                    "Producto de medición y atribución lanzado y cobrado por separado",
                    "Entregas a tiempo por encima del 85%",
                ],
                "anio3": [
                    "Time-to-market 40% menor que en 2026",
                    "La oferta integrada medios+producto+medición es el diferenciador de la plaza",
                ],
            },
        },
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
# 4) Logo (Pillow) — cuadrado navy con las iniciales "KM", PNG con transparencia
# ══════════════════════════════════════════════════════════════════════════════
def build_logo_png() -> bytes:
    """Genera el logo en memoria y lo pasa por el MISMO normalizador que usa la app
    (app/api/v1/company/service.normalize_logo): PNG RGBA, máx 600px de ancho."""
    from PIL import Image, ImageDraw, ImageFont

    size = 400
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))  # fondo transparente
    d = ImageDraw.Draw(img)

    # Cuadrado navy con esquinas redondeadas.
    d.rounded_rectangle([(0, 0), (size - 1, size - 1)], radius=56, fill=NAVY)

    # Iniciales "KM" centradas, en la fuente más grande disponible del sistema.
    texto = "KM"
    font = None
    for ruta in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            font = ImageFont.truetype(ruta, 176)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    x0, y0, x1, y1 = d.textbbox((0, 0), texto, font=font)
    d.text(
        ((size - (x1 - x0)) / 2 - x0, (size - (y1 - y0)) / 2 - y0),
        texto, font=font, fill=(255, 255, 255, 255),
    )

    # Subrayado de acento, para que no sea solo un cuadrado con letras.
    d.rectangle([(size * 0.30, size * 0.78), (size * 0.70, size * 0.78 + 12)],
                fill=(255, 255, 255, 200))

    out = BytesIO()
    img.save(out, format="PNG")
    return normalize_logo(out.getvalue(), "keting_media_logo.png")


# ══════════════════════════════════════════════════════════════════════════════
# 5) Board pack — dos PDFs realistas con reportlab, en memoria
# ══════════════════════════════════════════════════════════════════════════════
def _money(n: int) -> str:
    """Formato contable: los negativos van entre paréntesis, como en un P&L real."""
    return f"(${abs(n):,.0f})" if n < 0 else f"${n:,.0f}"


def _pct(n: float) -> str:
    return f"({abs(n):.1f}%)" if n < 0 else f"{n:.1f}%"


def _pdf_styles():
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib import colors

    ss = getSampleStyleSheet()
    navy = colors.HexColor(NAVY)
    return {
        "navy": navy,
        "titulo": ParagraphStyle("t", parent=ss["Title"], fontSize=20, leading=25,
                                 textColor=navy, spaceAfter=6),
        "sub": ParagraphStyle("s", parent=ss["Normal"], fontSize=10.5, leading=14,
                              textColor=colors.HexColor("#64748b"), spaceAfter=14),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontSize=13, leading=17,
                             textColor=navy, spaceBefore=14, spaceAfter=6),
        "body": ParagraphStyle("b", parent=ss["Normal"], fontSize=10, leading=14.5,
                               spaceAfter=8),
        "nota": ParagraphStyle("n", parent=ss["Normal"], fontSize=8.5, leading=12,
                               textColor=colors.HexColor("#64748b")),
    }


def _numerar_pagina(canvas, doc):
    """Pie con numeración: permite que el CFO cite «p. 2»."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4

    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#94a3b8"))
    canvas.drawString(2 * 28.35, 1.4 * 28.35, "Keting Media, S.A. de C.V. — Uso interno")
    canvas.drawRightString(A4[0] - 2 * 28.35, 1.4 * 28.35, f"Página {canvas.getPageNumber()}")
    canvas.restoreState()


def build_estado_resultados_pdf() -> bytes:
    """Estado de resultados 2026: tabla con números, 2 páginas, numeración de página."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)

    st = _pdf_styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title=f"Estado de resultados {EJERCICIO} — Keting Media",
        author="Keting Media",
    )

    def fila(concepto, monto, pct, bold=False, linea=False):
        return (concepto, _money(monto), _pct(pct), bold, linea)

    filas = [
        fila("Ingresos por servicios", INGRESOS, 100.0, bold=True),
        fila("(-) Costo de ventas (nómina de producción y proveedores)", -COSTO_VENTAS,
             -COSTO_VENTAS / INGRESOS * 100),
        fila("Utilidad bruta", MARGEN_BRUTO, MARGEN_BRUTO / INGRESOS * 100, bold=True, linea=True),
        fila("(-) Gastos de operación (admin., ventas, renta, sistemas)", -GASTOS_OPERACION,
             -GASTOS_OPERACION / INGRESOS * 100),
        fila("EBITDA", EBITDA, EBITDA / INGRESOS * 100, bold=True, linea=True),
        fila("(-) Depreciación y amortización", -DEP_AMORT, -DEP_AMORT / INGRESOS * 100),
        fila("Utilidad de operación", UTIL_OPERACION, UTIL_OPERACION / INGRESOS * 100, bold=True,
             linea=True),
        fila("(-) Gastos financieros netos", -GASTOS_FINANCIEROS,
             -GASTOS_FINANCIEROS / INGRESOS * 100),
        fila("Utilidad antes de impuestos", UTIL_ANTES_IMP, UTIL_ANTES_IMP / INGRESOS * 100,
             bold=True, linea=True),
        fila("(-) Impuestos a la utilidad (ISR)", -ISR, -ISR / INGRESOS * 100),
        fila("Utilidad neta", UTILIDAD_NETA, MARGEN_NETO_PCT, bold=True, linea=True),
    ]

    data = [["Concepto", "Monto (USD)", "% de ingresos"]]
    data += [[f[0], f[1], f[2]] for f in filas]

    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), st["navy"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
    ]
    for i, f in enumerate(filas, start=1):
        if f[3]:
            estilo.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
        if f[4]:
            estilo.append(("LINEABOVE", (0, i), (-1, i), 0.9, st["navy"]))
    estilo.append(("BACKGROUND", (0, len(filas)), (-1, len(filas)), colors.HexColor("#eef2f7")))

    tabla = Table(data, colWidths=[10.2 * cm, 3.6 * cm, 3.2 * cm], repeatRows=1)
    tabla.setStyle(TableStyle(estilo))

    flow = [
        Paragraph("Keting Media, S.A. de C.V.", st["titulo"]),
        Paragraph(
            f"Estado de resultados del ejercicio {EJERCICIO} — cifras en dólares estadounidenses "
            "(USD). Documento preparado para la sesión de consejo.", st["sub"]),
        tabla,
        Spacer(1, 0.5 * cm),
        Paragraph(
            f"<b>Lectura rápida:</b> la empresa facturó {_money(INGRESOS)} y retuvo "
            f"{_money(UTILIDAD_NETA)} de utilidad neta, un margen de "
            f"<b>{MARGEN_NETO_PCT:.1f}%</b>, frente al ~11% de referencia en agencias comparables. "
            f"El EBITDA fue de {_money(EBITDA)} ({_pct(EBITDA / INGRESOS * 100)}). El detalle de "
            "ingresos por cliente y las notas están en la página 2.", st["body"]),
        Paragraph(
            "Nota del preparador: el cierre contable del ejercicio se emitió 45 días después del "
            "corte. No existe costeo por proyecto, por lo que el costo de ventas se presenta "
            "agregado y no permite identificar la rentabilidad de cada cuenta.", st["nota"]),
        PageBreak(),
    ]

    # ── Página 2: desglose de ingresos por cliente + notas ────────────────────
    flow.append(Paragraph("Notas al estado de resultados", st["titulo"]))
    flow.append(Paragraph(f"Ejercicio {EJERCICIO} — página 2 de 2", st["sub"]))

    flow.append(Paragraph("Nota 1 — Concentración de ingresos por cliente", st["h2"]))
    dat2 = [["Cliente", "Ingreso (USD)", "% del total"]]
    for nombre, monto, pct in CLIENTES_TOP:
        dat2.append([nombre, _money(monto), _pct(pct)])
    dat2.append(["Subtotal top 3", _money(sum(c[1] for c in CLIENTES_TOP)),
                 _pct(CONCENTRACION_TOP3)])
    dat2.append([RESTO_CLIENTES[0], _money(RESTO_CLIENTES[1]), _pct(RESTO_CLIENTES[2])])
    dat2.append(["Total", _money(INGRESOS), "100.0%"])

    t2 = Table(dat2, colWidths=[10.2 * cm, 3.6 * cm, 3.2 * cm], repeatRows=1)
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), st["navy"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 4), (-1, 4), "Helvetica-Bold"),
        ("FONTNAME", (0, 6), (-1, 6), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEABOVE", (0, 4), (-1, 4), 0.9, st["navy"]),
        ("LINEABOVE", (0, 6), (-1, 6), 0.9, st["navy"]),
        ("BACKGROUND", (0, 6), (-1, 6), colors.HexColor("#eef2f7")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
    ]))
    flow.append(t2)
    flow.append(Spacer(1, 0.35 * cm))
    flow.append(Paragraph(
        f"Los tres clientes principales concentran el <b>{CONCENTRACION_TOP3:.0f}%</b> de los "
        f"ingresos del ejercicio. La utilidad neta del año ({_money(UTILIDAD_NETA)}) es inferior al "
        f"ingreso anual de cualquiera de ellos: la pérdida de una sola cuenta convertiría el "
        f"ejercicio en pérdida.", st["body"]))

    flow.append(Paragraph("Nota 2 — Estructura de costos y capacidad", st["h2"]))
    flow.append(Paragraph(
        f"El costo de ventas ({_money(COSTO_VENTAS)}, {_pct(COSTO_VENTAS / INGRESOS * 100)} de los "
        f"ingresos) corresponde en un 78% a nómina del equipo de producción. Solo el "
        f"{HORAS_FACTURABLES:.0f}% de las horas disponibles del equipo se facturaron; el resto se "
        f"consumió en retrabajos, juntas internas y capacidad ociosa que se paga igual.", st["body"]))

    flow.append(Paragraph("Nota 3 — Capital de trabajo", st["h2"]))
    flow.append(Paragraph(
        f"Las cuentas por cobrar promediaron {DIAS_COBRO} días (política comercial: 30 días). La "
        f"razón corriente al cierre fue de {RAZON_CORRIENTE}x. La empresa financia a sus clientes "
        f"con su propio capital de trabajo.", st["body"]))

    flow.append(Paragraph("Nota 4 — Personal", st["h2"]))
    flow.append(Paragraph(
        f"La plantilla promedio del ejercicio fue de {EMPLEADOS} personas. La rotación anual fue de "
        f"<b>{ROTACION_PCT:.0f}%</b>; el costo de reclutamiento, contratación y curva de aprendizaje "
        f"asociado no se registra por separado y está absorbido dentro de los gastos de operación.",
        st["body"]))

    flow.append(Spacer(1, 0.4 * cm))
    flow.append(Paragraph(
        "Estados financieros internos, no auditados. Preparados por la administración de Keting "
        "Media, S.A. de C.V.", st["nota"]))

    doc.build(flow, onFirstPage=_numerar_pagina, onLaterPages=_numerar_pagina)
    return buf.getvalue()


def build_presentacion_pdf() -> bytes:
    """Presentación estratégica: 4 páginas (situación, concentración, expansión, decisiones)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)

    st = _pdf_styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title=f"Presentación estratégica {EJERCICIO} — Keting Media",
        author="Keting Media",
    )

    def bullets(items):
        return [Paragraph(f"•&nbsp;&nbsp;{t}", st["body"]) for t in items]

    def tabla_simple(data, anchos):
        t = Table(data, colWidths=anchos, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), st["navy"]),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ]))
        return t

    flow = []

    # ── Página 1: situación del negocio ──────────────────────────────────────
    flow.append(Paragraph("Keting Media — Situación del negocio", st["titulo"]))
    flow.append(Paragraph(
        f"Material para la sesión de consejo · Ejercicio {EJERCICIO} · Uso interno", st["sub"]))
    flow.append(Paragraph("Dónde estamos", st["h2"]))
    flow.append(Paragraph(
        f"Cerramos {EJERCICIO} con {_money(INGRESOS)} de ingresos y {_money(UTILIDAD_NETA)} de "
        f"utilidad neta: un margen del {MARGEN_NETO_PCT:.0f}%. Crecimos "
        f"{CRECIMIENTO_VENTAS:.0f}% contra el año anterior, por debajo de lo que crece el mercado. "
        f"Somos {EMPLEADOS} personas y llevamos 22 años operando.", st["body"]))

    flow.append(tabla_simple([
        ["Indicador", f"{EJERCICIO}", "Referencia"],
        ["Ingresos anuales", _money(INGRESOS), "—"],
        ["Margen bruto", "37.0%", "45%"],
        ["EBITDA", _money(EBITDA), "—"],
        ["Margen neto", f"{MARGEN_NETO_PCT:.0f}%", "11%"],
        ["Crecimiento de ventas", f"{CRECIMIENTO_VENTAS:.0f}%", "15%"],
        ["Concentración top-3 clientes", f"{CONCENTRACION_TOP3:.0f}%", "< 30%"],
        ["Rotación de personal", f"{ROTACION_PCT:.0f}%", "15%"],
        ["Días de cierre contable", f"{DIAS_CIERRE} días", "10 días"],
        ["Horas facturables", f"{HORAS_FACTURABLES:.0f}%", "75%"],
    ], [8.0 * cm, 4.5 * cm, 4.5 * cm]))
    flow.append(Spacer(1, 0.4 * cm))

    flow.append(Paragraph("Lo que nos está funcionando", st["h2"]))
    flow.extend(bullets([
        "La marca vende sola: los clientes grandes llegan por recomendación, sin equipo comercial.",
        "Somos los únicos en la plaza que ofrecemos medios y desarrollo de producto en la misma mesa.",
        "El núcleo de líderes (5 personas) tiene más de 6 años en la casa y conoce a los clientes.",
        "La empresa es rentable y no tiene deuda bancaria significativa.",
    ]))
    flow.append(Paragraph("Lo que nos está frenando", st["h2"]))
    flow.extend(bullets([
        f"Ganamos poco para lo que facturamos: {MARGEN_NETO_PCT:.0f}% de margen neto contra ~11% de "
        f"la industria.",
        f"Se nos va un tercio del equipo cada año (rotación {ROTACION_PCT:.0f}%).",
        f"Cerramos el mes en {DIAS_CIERRE} días y no tenemos costeo por proyecto: no sabemos qué "
        f"cuenta gana y cuál pierde.",
        "Toda decisión pasa por la dirección general: crecemos hasta donde alcanzan sus horas.",
    ]))
    flow.append(PageBreak())

    # ── Página 2: concentración de clientes ──────────────────────────────────
    flow.append(Paragraph("El riesgo número uno: la concentración", st["titulo"]))
    flow.append(Paragraph(
        f"El {CONCENTRACION_TOP3:.0f}% de nuestros ingresos vive en tres cuentas", st["sub"]))

    dat = [["Cliente", "Ingreso (USD)", "% del total"]]
    for nombre, monto, pct in CLIENTES_TOP:
        dat.append([nombre, _money(monto), _pct(pct)])
    dat.append(["Subtotal top 3", _money(sum(c[1] for c in CLIENTES_TOP)), _pct(CONCENTRACION_TOP3)])
    dat.append([RESTO_CLIENTES[0], _money(RESTO_CLIENTES[1]), _pct(RESTO_CLIENTES[2])])
    dat.append(["Total", _money(INGRESOS), "100.0%"])
    flow.append(tabla_simple(dat, [8.0 * cm, 4.5 * cm, 4.5 * cm]))
    flow.append(Spacer(1, 0.4 * cm))

    flow.append(Paragraph("Por qué nos quita el sueño", st["h2"]))
    flow.extend(bullets([
        f"Nuestra utilidad de todo el año ({_money(UTILIDAD_NETA)}) es menor que lo que nos factura "
        f"cualquiera de las tres cuentas. Perder una convierte el año en pérdida.",
        "Las tres cuentas se renegocian anualmente. En la práctica, nuestra estrategia se decide en "
        "esas tres mesas, no en la nuestra.",
        "Banca Prisma está armando su propio equipo digital interno. No van a cambiar de agencia: "
        "van a dejar de necesitar una.",
        "No tenemos proceso de prospección. Nuestra venta es 100% reactiva: si no nos recomiendan, "
        "no entra nada nuevo.",
    ]))
    flow.append(Paragraph(
        "Este es el punto donde queremos la opinión del consejo: cómo bajamos la concentración sin "
        "descuidar a las cuentas que hoy pagan la nómina.", st["body"]))
    flow.append(PageBreak())

    # ── Página 3: planes de expansión ────────────────────────────────────────
    flow.append(Paragraph("Hacia dónde queremos ir", st["titulo"]))
    flow.append(Paragraph(f"Plan de expansión {EJERCICIO + 1}–{ANIO_OBJETIVO}", st["sub"]))

    flow.append(Paragraph("La apuesta", st["h2"]))
    flow.append(Paragraph(
        f"Duplicar la facturación a {ANIO_OBJETIVO} y llegar ahí con un margen sano, una cartera "
        "diversificada y una empresa que no dependa de que la dirección general apruebe todo. La "
        "demanda existe: el nearshoring está trayendo corporativos al norte y los clientes están "
        "migrando de comprar campañas a comprar producto y medición, que es exactamente lo que "
        "sabemos hacer y hoy regalamos dentro de los proyectos.", st["body"]))

    flow.append(Paragraph("Las tres iniciativas de crecimiento", st["h2"]))
    flow.extend(bullets([
        "<b>Prospección activa.</b> Un responsable comercial, un pipeline y una meta de 4 clientes "
        "nuevos fuera del top-3 en el primer año.",
        "<b>Nuevo segmento.</b> Entrar a manufactura y nearshoring, fuera del retail y la banca, con "
        "dos cuentas ancla.",
        "<b>Producto de medición.</b> Empaquetar y cobrar por separado la atribución y los "
        "dashboards que hoy incluimos gratis.",
    ]))

    flow.append(Paragraph("Lo que tenemos que ordenar antes de crecer", st["h2"]))
    flow.extend(bullets([
        "Costeo por proyecto y cierre contable en 10 días: hoy decidimos con números de hace mes y medio.",
        "Plan de carrera y compensación variable: sin frenar la rotación, crecer significa reconstruir "
        "el equipo dos veces.",
        "Delegación formal y comité de dirección: si todo sigue pasando por una sola firma, duplicar "
        "el tamaño duplica el cuello de botella.",
        "Adoptar IA en producción antes de que la competencia la use para bajarnos el precio.",
    ]))
    flow.append(Paragraph(
        "Nuestra lectura es que crecer sobre la estructura actual duplicaría los ingresos y los "
        "problemas al mismo tiempo. Primero medimos, luego ordenamos, y solo entonces expandimos.",
        st["body"]))
    flow.append(PageBreak())

    # ── Página 4: qué le pedimos al consejo ──────────────────────────────────
    flow.append(Paragraph("Qué le pedimos al consejo", st["titulo"]))
    flow.append(Paragraph("Las decisiones que traemos a esta sesión", st["sub"]))

    flow.append(tabla_simple([
        ["Decisión", "Impacto", "Urgencia"],
        ["Invertir en costeo por proyecto y cierre a 10 días", "Margen", "Inmediata"],
        ["Contratar un responsable comercial", "Concentración", "Alta"],
        ["Plan de carrera + compensación variable", "Rotación", "Alta"],
        ["Instalar el consejo consultivo formal", "Gobierno", "Alta"],
        ["Piloto de IA en producción", "Margen bruto", "Media"],
        ["Protocolo familiar y plan de sucesión", "Continuidad", "Media"],
        ["Registrar la marca ante el IMPI", "Legal", "Baja"],
    ], [9.0 * cm, 4.0 * cm, 4.0 * cm]))
    flow.append(Spacer(1, 0.5 * cm))

    flow.append(Paragraph("La pregunta de fondo", st["h2"]))
    flow.append(Paragraph(
        "¿Qué hacemos primero: salimos a crecer para diluir la concentración, o arreglamos la "
        "estructura antes de meterle volumen? La dirección general se inclina por lo segundo, pero "
        "cada trimestre que pasa sin clientes nuevos es un trimestre más de dependencia de tres "
        "cuentas. Queremos que el consejo nos contradiga si estamos equivocados.", st["body"]))

    flow.append(Spacer(1, 0.4 * cm))
    flow.append(Paragraph(
        "Documento interno de Keting Media, S.A. de C.V. Las cifras provienen del estado de "
        f"resultados {EJERCICIO} no auditado que acompaña a esta presentación.", st["nota"]))

    doc.build(flow, onFirstPage=_numerar_pagina, onLaterPages=_numerar_pagina)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# Siembra
# ══════════════════════════════════════════════════════════════════════════════
async def main(email: str) -> None:
    hoy = date.today()
    ahora = datetime.now(timezone.utc)

    # Los PDFs y el logo se generan ANTES de tocar la DB: si reventaran (fuente,
    # reportlab, Pillow), no dejamos la cuenta a medio sembrar.
    print("Generando logo y board pack (Pillow + reportlab)…")
    logo_png = build_logo_png()
    pdf_finanzas = build_estado_resultados_pdf()
    pdf_presentacion = build_presentacion_pdf()
    print(f"  - logo PNG               {len(logo_png):>8,} bytes")
    print(f"  - estado_resultados.pdf  {len(pdf_finanzas):>8,} bytes")
    print(f"  - presentacion.pdf       {len(pdf_presentacion):>8,} bytes\n")

    async with AsyncSessionLocal() as db:
        # ── 0) user_id real desde Supabase Auth ──────────────────────────────
        row = (await db.execute(
            text("SELECT id FROM auth.users WHERE email = :email"), {"email": email}
        )).first()
        if not row:
            print(f"❌ No existe un usuario en auth.users con el correo {email!r}. "
                  f"Regístrate primero en la app con ese correo y vuelve a correr el script.")
            return
        user_id = str(row[0])
        print(f"Usuario: {email} (user_id={user_id})")

        # ── 1) Reset (idempotencia): misma lógica que scripts/reset_user_data ─
        print("Borrando datos previos del usuario…")
        borradas = 0
        for label, sql in _RESET_STEPS:
            n = (await db.execute(text(sql), {"uid": user_id})).rowcount or 0
            borradas += n
            if n:
                print(f"  - {label:28s} {n} fila(s)")
        print(f"  → {borradas} fila(s) borradas.\n")

        # ── 2) OnboardingSession completo ────────────────────────────────────
        onboarding = OnboardingSession(
            user_id=user_id,
            completed_stages=[1, 2, 3, 4, 5, 6, 7, 8],
            memory_buffer=MEMORY_BUFFER,
            governance_score=GOVERNANCE_SCORE,
            completed_at=ahora,
        )
        db.add(onboarding)
        await db.flush()

        # ── 3) DiagnosticoEstrategico activo (con FODA activo) ───────────────
        diag = DiagnosticoEstrategico(
            user_id=user_id,
            status="active",
            content=build_diagnostico_content(),
        )
        db.add(diag)

        # ── 4) AnnualPlan con roadmap en borrador ────────────────────────────
        plan = AnnualPlan(
            user_id=user_id,
            title="Plan estratégico de 3 año(s)",
            start_date=hoy,
            status="active",
            horizon_years=3,
            roadmap=ROADMAP,
            roadmap_status="borrador",
            diagnostico_summary=(
                "Empresa técnicamente sólida y financieramente frágil: 4.2 MDD de facturación con "
                "6% de margen neto, 58% de los ingresos en 3 cuentas, 31% de rotación y una "
                "dirección que es el cuello de botella de toda decisión."
            ),
        )
        db.add(plan)

        # ── 5) CompanyLogo (mismo procesamiento que la app) ──────────────────
        await upsert_logo(user_id, logo_png, db)

        # ── 6) BoardSession del periodo, SIN análisis ────────────────────────
        board = BoardSession(
            onboarding_session_id=onboarding.id,
            user_id=user_id,
            period_year=hoy.year,
            period_month=hoy.month,
            status="draft",
            profile_snapshot=dict(MEMORY_BUFFER),
            governance_score_snapshot=GOVERNANCE_SCORE,
        )
        db.add(board)
        await db.flush()

        # ── 7) Board pack: PDFs a storage + filas Document ───────────────────
        pack = [
            (f"estado_resultados_{EJERCICIO}.pdf", "financial", pdf_finanzas),
            ("presentacion_estrategica.pdf", "presentation", pdf_presentacion),
        ]
        for filename, doc_type, content in pack:
            doc_id = uuid.uuid4()
            s3_key = generate_storage_key(board.id, doc_id, filename)
            await upload_to_storage(content, s3_key)
            db.add(Document(
                id=doc_id,
                session_id=onboarding.id,
                board_session_id=board.id,
                user_id=user_id,
                document_type=doc_type,
                filename=filename,
                s3_key=s3_key,
                processing_status="pending",
            ))

        await db.commit()

        _resumen(email, user_id, onboarding.id, board.id, plan.id, hoy)


_MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def _resumen(email, user_id, onboarding_id, board_id, plan_id, hoy) -> None:
    periodo = f"{_MESES[hoy.month].capitalize()} {hoy.year}"
    print("═" * 78)
    print(f"✅ Cuenta de demo lista para {email}")
    print("═" * 78)
    print(f"  user_id               {user_id}")
    print(f"  onboarding_session_id {onboarding_id}")
    print(f"  board_session_id      {board_id}")
    print(f"  annual_plan_id        {plan_id}")
    print()
    print("SEMBRADO")
    print(f"  • OnboardingSession   Keting Media · 8/8 etapas · {EMPLEADOS} empleados · "
          f"{_money(INGRESOS)} · familiar 2ª gen.")
    print(f"                        KPIs reales (margen neto {MARGEN_NETO_PCT:.0f}%, rotación "
          f"{ROTACION_PCT:.0f}%, top-3 {CONCENTRACION_TOP3:.0f}%, cierre {DIAS_CIERRE} días)")
    print("                        vision.exito_consejo (la definición de éxito del dueño)")
    print("                        hallazgos en las 7 áreas")
    print(f"  • Diagnóstico         status=active · 6 secciones · {len(RIESGOS)} riesgos · "
          f"PESTEL · {len(FUENTES)} fuentes")
    print("  • FODA                foda_status=active (4 cuadrantes + síntesis + metas)")
    print(f"  • AnnualPlan          status=active · roadmap_status=BORRADOR · horizonte "
          f"{ANIO_OBJETIVO} · {len(ROADMAP['pilares'])} pilares")
    print("  • CompanyLogo         cuadrado navy «KM», PNG")
    print(f"  • BoardSession        {periodo} · status=draft · SIN análisis (a propósito)")
    print(f"  • Board pack          estado_resultados_{EJERCICIO}.pdf (financial, 2 pp. numeradas) "
          f"+ presentacion_estrategica.pdf (presentation, 4 pp.)")
    print()
    print("QUÉ HACER PARA VER CADA FEATURE")
    print("  1. Entra a la app con ese correo → Dashboard.")
    print("  2. Datos (/dashboard/datos)")
    print("     · Perfil, KPIs con valores reales, hallazgos por área, FODA y el logo «KM».")
    print("     · Ahí mismo puedes reemplazar el logo (LogoUpload).")
    print("  3. Diagnóstico (/dashboard/diagnostico)")
    print("     · Las 6 secciones, fortalezas/debilidades por área, los riesgos con su severidad")
    print("       y las fuentes. Descarga el PDF del diagnóstico.")
    print("  4. FODA")
    print("     · Ya está en 'active': se ve la matriz completa y el PDF, sin regenerarla.")
    print("  5. Plan → Roadmap")
    print("     · Aquí está lo nuevo: banner de BORRADOR (dale «Validar roadmap» para verlo pasar")
    print("       a validado), timeline pilares × 3 años con los temas del año («Ordenar la casa»,")
    print("       «Expandir el negocio», «Consolidar el liderazgo»), metas hoy→meta con el target")
    print("       VACÍO (lo pone el dueño), KPIs por pilar, resultados esperados y el PDF del deck.")
    print(f"  6. Consejo → sesión de {periodo}")
    print("     · La sesión ya trae el board pack (los 2 PDFs) y NO tiene análisis.")
    print("     · Captura los KPIs del periodo y dale «Analizar»: verás a los 4 consejeros leer los")
    print("       documentos. El CFO puede citar «p. 2» del estado de resultados (la nota de")
    print(f"       concentración: {CONCENTRACION_TOP3:.0f}% en 3 cuentas y utilidad neta de "
          f"{_money(UTILIDAD_NETA)}).")
    print("     · Los números de los PDFs coinciden con los KPIs del onboarding: si el consejo")
    print("       detecta la contradicción (crecer con 3 clientes y 6% de margen), la demo funciona.")
    print()
    print("  Idempotente: puedes volver a correr este mismo comando cuantas veces quieras.")
    print("═" * 78)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: venv/bin/python -m scripts.seed_demo_completo correo@ejemplo.com")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
