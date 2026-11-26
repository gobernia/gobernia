"""La herramienta `registrar_avance` de Todd (dueño y responsable) y cómo se leen sus datos.
Sin base de datos ni almacenamiento: lo usan los módulos de IA. Lo que guarda el PDF en la tarea
está en app/services/avance_todd.py."""

# Lo que Todd debe juntar antes de guardar (lo pide la herramienta registrar_avance).
REGISTRAR_AVANCE_TOOL = {
    "name": "registrar_avance",
    "description": (
        "Guarda en una tarea lo que la persona contó que hicieron, cuando NO tiene un documento "
        "para subir. Queda como evidencia de la tarea y el Auditor la revisa. Úsala solo cuando ya "
        "sepas qué se hizo y con qué resultado concreto; usa sus palabras y no inventes nada."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "El id EXACTO de la tarea."},
            "que_se_hizo": {"type": "string", "description": "Qué se hizo, con sus palabras."},
            "cuando": {"type": "string", "description": "Cuándo se hizo (fecha o periodo), si lo dijo."},
            "quien": {"type": "string", "description": "Quién participó, si lo dijo."},
            "resultado": {"type": "string",
                          "description": "Resultado concreto: cifras, nombres, fechas o lo que quedó listo."},
        },
        "required": ["task_id", "que_se_hizo", "resultado"],
    },
}


def datos_del_avance(entrada: dict) -> dict:
    return {k: str(entrada.get(k) or "").strip() for k in ("que_se_hizo", "cuando", "quien", "resultado")}
