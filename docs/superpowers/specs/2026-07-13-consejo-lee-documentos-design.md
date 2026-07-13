# El consejo lee el board pack

**Fecha:** 2026-07-13
**Origen:** el prompt del "Consejero Externo de Grupo MISOL" del cliente.

## El hallazgo que reencuadra la feature

No hay que construir un consejero nuevo. **El "Consejero Externo" es el consejo que ya existe** (CFO, CSO, CRO, Auditor + Abogado del Diablo). Lo que le falta es una capacidad: **leer los documentos del cliente**. Hoy analizan solo con lo que Todd capturó — opinan sin haber visto un estado financiero.

Estado actual relevante:
- `Document.board_session_id` **ya existe** en el esquema (con su migración) y **nadie lo escribe nunca**.
- `month_review.py` **ya manda PDFs a Claude** como `document` blocks en base64. Claude lee PDFs nativamente: no hace falta extraer texto (el extractor con pdfplumber existe pero sus librerías nunca se instalaron — código muerto).
- **No existe UI para subir ningún documento.** El endpoint de la etapa 7 no lo llama nadie.
- Los agentes del consejo son **los únicos del sistema con salida de texto libre parseada con regex**; el resto usa tool-use forzado.

## Diseño

### 1. Board pack por sesión
Nueva sección en la pantalla de la sesión de consejo: subir documentos con su tipo. Van a Supabase Storage (recién configurado) y se guardan como `Document` con `board_session_id`.

Tipos nuevos (se suman a los existentes): `financial` (ya existe), `presentation`, `audit_plan`, `other`.

API:
- `POST /board-sessions/{id}/documents` — multipart (`file`, `document_type`)
- `GET /board-sessions/{id}/documents` → lista
- `DELETE /board-sessions/{id}/documents/{doc_id}`

### 2. Cada consejero lee lo que le compete
Ruteo por rol (un documento puede ir a varios agentes):

| Agente | Lee |
|---|---|
| CFO | `financial`, `business_plan` |
| Auditor | `audit_plan`, `financial`, `internal_rules`, `bylaws` |
| CSO | `presentation`, `business_plan` |
| CRO | `financial`, `audit_plan`, `presentation` |

Los documentos se adjuntan **solo en el análisis inicial** de cada agente (`run_agent_analysis`), no en la crítica ni en la revisión: esas trabajan sobre lo que el agente escribió, no sobre los papeles.

Formatos legibles por Claude: PDF e imágenes. Los `.xlsx`/`.docx` no se adjuntan; se le avisa al agente con una nota ("hay un Excel que no puedo leer; pídele al dueño subirlo en PDF") — mismo patrón que `month_review.select_review_documents`.

### 3. Salida estructurada con fuente y semáforo
Los agentes pasan a **tool-use forzado** (como el resto del sistema). Nuevo esquema:

```
{
  summary: str,
  findings: [{texto: str, fuente: str}],       # fuente = "Estado de resultados, p. 4" o "" si no viene de un documento
  alerts:  [{nivel: "rojo"|"ambar"|"verde", texto: str, fuente: str}],
  recommendations: [str],
  preguntas: [str],                            # preguntas detonadoras para la junta, desde su rol
}
```

**Regla antialucinación:** si el agente afirma algo tomado de un documento, DEBE citar la fuente. Si no tiene documento que lo respalde, `fuente` va vacía y no puede presentarlo como dato duro.

**Retrocompatibilidad:** las sesiones ya guardadas tienen `findings`/`alerts` como listas de strings. El frontend normaliza ambos shapes; nada se rompe.

### 4. Frontend
- Sección de documentos en la sesión (subir/listar/borrar), plantilla: `EvidenceSection.tsx`.
- Los hallazgos muestran su fuente como una cita discreta.
- Las alertas se pintan con el semáforo (rojo/ámbar/verde).
- Bloque nuevo de "Preguntas para la junta" por consejero.

## Fuera de alcance
- Extracción de texto / RAG / embeddings: innecesario, Claude lee los PDFs.
- Que el diagnóstico inicial lea documentos (decisión: solo la sesión de consejo).
- Monday.
