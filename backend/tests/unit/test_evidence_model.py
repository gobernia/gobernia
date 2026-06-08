from app.models import Base
from app.models.evidence import Evidence
from app.models.action_plan import ActionTask


def test_evidences_table_registered():
    table = Base.metadata.tables.get("evidences")
    assert table is not None
    cols = set(table.columns.keys())
    assert {"id", "action_task_id", "filename", "s3_key",
            "content_type", "size_bytes", "created_at"} <= cols


def test_action_task_has_evidences_relationship():
    assert hasattr(ActionTask, "evidences")


def test_evidence_instantiable():
    e = Evidence(action_task_id=None, filename="a.pdf", s3_key="k",
                 content_type="application/pdf", size_bytes=10)
    assert e.filename == "a.pdf"
