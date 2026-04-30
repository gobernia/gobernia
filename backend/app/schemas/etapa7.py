from pydantic import BaseModel

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

DOCUMENT_TYPE_LABELS = {
    "financial":   "Estados financieros",
    "org_chart":   "Organigrama",
    "bylaws":      "Acta constitutiva / Estatutos",
    "business_plan": "Plan de negocios",
    "internal_rules": "Reglamento interno",
    "family_protocol": "Protocolo familiar",
    "other":       "Otro",
}


class DocumentMeta(BaseModel):
    document_id: str
    filename: str
    document_type: str
    document_type_label: str
    file_size_kb: float
    status: str   # pending | processing | completed | failed


class DocumentUploadResponse(BaseModel):
    document_id: str
    session_id: str
    filename: str
    document_type: str
    document_type_label: str
    status: str
    file_size_kb: float
    message: str


class Etapa7Output(BaseModel):
    session_id: str
    completed_stages: list[int]
    document_count: int
    documents: list[DocumentMeta]
    next_stage: int
