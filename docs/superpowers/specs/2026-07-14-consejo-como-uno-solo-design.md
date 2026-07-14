# El Consejo como un solo órgano + el Roadmap como eje

**Fecha:** 2026-07-14
**Origen:** documento del cliente "Flujo del Roadmap Estratégico en Gobernia" (10 puntos).

## El reencuadre

El documento no pide features sueltas: pide una **columna vertebral**. El Roadmap validado es el
documento rector, y todo el Consejo gira alrededor de él. Hoy el Roadmap está **completamente
desconectado del Consejo** (ningún agente lo lee) y los consejeros producen **cuatro opiniones
separadas** en vez de una conclusión.

Cita textual del cliente: *"el resultado esperado no son cuatro opiniones distintas, sino una única
conclusión del Consejo"* y *"ninguna actividad existe aislada; toda tarea debe contribuir
directamente al cumplimiento del Roadmap"*.

## Alcance de ESTE spec (el punto 1 del plan acordado)

### 1. El Roadmap entra al Consejo
`run_agent_analysis` recibe el **roadmap validado** (si no hay, lo dice explícitamente). Los cuatro
consejeros analizan contra dos insumos: **el Roadmap** (el plan de largo plazo del dueño) y **los
documentos de la sesión** (el board pack).

### 2. El Consejo emite UNA conclusión
Paso nuevo de **deliberación** al final del pipeline: los 4 análisis + las críticas del Abogado del
Diablo + el Roadmap + los KPIs entran a una síntesis (Opus, tool-use) que produce:

```
{
  conclusion: str,            # la voz del Consejo, no un resumen de resúmenes
  avance_roadmap: str,        # cómo va la empresa contra su Roadmap, con evidencia
  riesgos: [{nivel, texto, fuente}],
  acuerdos: [{
     texto, responsable_sugerido, fecha_sugerida, prioridad: alta|media|baja,
     pilar: str,              # el pilar del Roadmap al que sirve (o "" si es transversal)
     racional: str,
  }],
}
```

**Regla antialucinación (se mantiene):** toda afirmación tomada de un documento cita su fuente; sin
documento que la respalde, no se presenta como dato duro.

### 3. Los acuerdos son objetos reales, atados al Roadmap
Los acuerdos de la conclusión se materializan como filas `Compromiso` (el modelo que ya existe, con
su seguimiento y su link público para el responsable), extendido con:
- `board_session_id` — de qué sesión nació.
- `prioridad` — alta/media/baja.
- `pilar` — **el vínculo con el Roadmap**. Es el campo que hace posible medir avance y, más
  adelante, el tablero de 12 sesiones.
- `responsable_email` pasa a ser **opcional**: la IA propone un responsable por rol
  ("Dirección General"), el dueño le pone nombre y correo.

### 4. La pantalla de la sesión cambia de forma
Deja de ser cuatro tarjetas. Lidera **la conclusión del Consejo**, luego **el avance del Roadmap**,
luego **los acuerdos** (editables: el dueño asigna responsable y fecha). Las cuatro voces quedan
abajo, en un desplegable **"Cómo lo deliberó el Consejo"** — se ve una sola voz, pero se puede
auditar de dónde salió.

### 5. El Roadmap se versiona
El documento exige que el Roadmap validado quede **bloqueado y trazable**. Decisión del usuario:
- Al **validar**, aparece un **diálogo de confirmación** que enumera las consecuencias (se vuelve la
  guía oficial del Consejo, todas las sesiones giran alrededor de él, las recomendaciones se alinean
  a él, deja de ser editable).
- Al **reabrir**, la versión validada **se archiva intacta** (tabla `roadmap_versions`) y se trabaja
  sobre una **v2** en borrador. La Biblioteca lista **todas** las versiones validadas, cada una en
  solo lectura. Nadie queda encerrado por una errata y no se pierde el historial.

## Fuera de alcance (siguientes pasos, ya acordados)
- Tablero anual de 12 sesiones de consejo y continuidad automática (arrastrar acuerdos pendientes).
- Orden del día completa (board pack financiero + avance del Roadmap) atada a la sesión.
- Biblioteca con todos los reportes (diagnóstico, FODA, minutas, órdenes del día).
- Todd secretario proactivo (requiere un proceso programado que hoy no existe).
- Unificar `ActionTask` y `Compromiso` (hoy conviven dos modelos de "acuerdo").
