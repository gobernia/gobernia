# Roadmap Estratégico — alineación con el template + deck PDF

**Fecha:** 2026-07-13
**Origen:** template del cliente (`Template Strat Plan.pdf`, 10 láminas 16:9).

## Principio rector

**El template es una guía, no un formulario.** La IA decide qué información incluye con base en lo
que el consejo realmente sabe (diagnóstico, FODA, riesgos, entorno, KPIs de Todd). Si no tiene
evidencia para un bloque, lo deja vacío y ese bloque/lámina **no se renderiza** — ni en pantalla ni
en el PDF. Nada de rellenar con humo.

**Invariante que se mantiene:** la IA **nunca inventa un número meta/target**. Escribe el KPI y el
valor actual (que Todd sí captura); el objetivo numérico lo fija el dueño.

## Láminas del template → fuente de datos

| Lámina | Contenido | Fuente |
|---|---|---|
| 1 Portada | Logo cliente, "Roadmap Estratégico al {año}", fecha | `anio_objetivo` + fecha de generación (logo: pendiente, bloque 2) |
| 2 Panorama de retos y oportunidades | Situación actual, problemas estructurales, conclusión ejecutiva | `resumen_foda` + `conclusion_diagnostico` (nuevo) |
| 3 Tendencias externas | Tendencias con impacto + conclusión estratégica | `resumen_entorno` + `conclusion_entorno` (nuevo) |
| 4 Lámina maestra | Misión, visión, objetivos estratégicos, pilares con KPIs, estrategias clave, key enablers | `mision`, `vision`, `objetivos_estrategicos` (nuevo), `pilares[].kpis`/`.estrategias` (nuevos), `key_enablers` (nuevo) |
| 5–9 Una por pilar | Objetivo, estrategias, plan de implementación por fases, KPIs actual→meta, resultados esperados | `pilares[]`: `objetivo`, `estrategias`, `milestones` + `fases[].titulo`, `kpis`, `resultados_esperados` (todos nuevos salvo milestones) |
| 10 Plan de ejecución | Matriz pilares × años con tema por año | `pilares[].milestones` (ya existe) + `temas_por_anio` (nuevo) |

## Esquema del roadmap (campos nuevos, todos opcionales)

```
{
  anio_objetivo: int|null,            # p.ej. 2029; si falta, se calcula año actual + 3
  vision, mision, propuesta_valor,    # ya existen
  objetivos_estrategicos: [str],      # nuevo
  key_enablers: [str],                # nuevo
  temas_por_anio: {anio1, anio2, anio3},   # nuevo — p.ej. "Ordenar la casa"
  conclusion_diagnostico: str,        # nuevo
  conclusion_entorno: str,            # nuevo
  metas_3anios: [{meta, kpi, valor_actual, target=""}],   # ya existe
  resumen_foda, resumen_entorno,      # ya existen
  pilares: [{
    nombre, descripcion, milestones{anio1,anio2,anio3},   # ya existen
    objetivo: str,                                        # nuevo
    estrategias: [str],                                   # nuevo (0-4)
    kpis: [{label, actual, meta=""}],                     # nuevo — `meta` SIEMPRE vacío
    resultados_esperados: [{titulo, descripcion}],        # nuevo (0-3)
    fases: {anio1: {titulo}, anio2: {titulo}, anio3: {titulo}}   # nuevo — título de cada fase
  }]
}
```

**Retrocompatibilidad:** un roadmap guardado con el esquema viejo abre sin error; los campos nuevos
llegan vacíos y sus bloques no se muestran. No hay migración de datos ni columnas nuevas.

## PDF: deck 16:9

`build_roadmap_pdf` pasa de documento carta vertical a **presentación apaisada** (landscape A4/16:9),
una lámina por página, **saltándose las láminas sin datos**. Sin fotos: color, tipografía y diagramas.

- Paleta por pilar: la misma que el timeline del frontend (`_PILAR_COLORS`).
- KPI actual → meta: barra/flecha con los dos valores; si no hay meta, se muestra "meta: por definir".
- Lámina 10: tabla pilares × 3 años con el tema del año como encabezado.
- Portada: navy a sangre, nombre de empresa, "Roadmap Estratégico al {año}", fecha. Espacio reservado
  arriba-izquierda para el logo del cliente (se conecta cuando exista el upload de logo).

## Frontend

Las secciones nuevas se muestran en la pestaña Plan → Roadmap y se editan con el mismo patrón de hoy
(`EditControls` por bloque), y quedan bloqueadas cuando el roadmap está validado. Bloques vacíos no se
renderizan; en modo edición sí aparecen (vacíos) para que el dueño los pueda llenar.

## Fuera de alcance

- Logo del cliente (bloque 2, ya acordado).
- Imágenes por pilar.
- Plan de trabajo a 12 meses (entregable aparte).
