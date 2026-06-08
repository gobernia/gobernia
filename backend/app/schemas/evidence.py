from datetime import datetime

from pydantic import BaseModel


class EvidenceOut(BaseModel):
    id: str
    action_task_id: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
