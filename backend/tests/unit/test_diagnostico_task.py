from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.tasks.diagnostico_tasks import _run_generation


@pytest.mark.asyncio
async def test_run_generation_ok():
    diag = MagicMock(); diag.user_id = "u1"; diag.status = "generating"
    onb = MagicMock(); onb.memory_buffer = {"company": {"name": "ACME"}}
    diag_res = MagicMock(); diag_res.scalar_one_or_none.return_value = diag
    onb_res = MagicMock(); onb_res.scalars.return_value.first.return_value = onb
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[diag_res, onb_res]); db.commit = AsyncMock()

    fake_content = {"sections": [{"key": "resumen_ejecutivo", "title": "X", "body": "ok"}], "sources": []}
    with patch("app.tasks.diagnostico_tasks.generate_diagnostico", return_value=fake_content):
        await _run_generation("d1", db)

    assert diag.status == "active"
    assert diag.content == fake_content


@pytest.mark.asyncio
async def test_run_generation_marca_failed_en_error():
    diag = MagicMock(); diag.user_id = "u1"; diag.status = "generating"
    onb = MagicMock(); onb.memory_buffer = {}
    diag_res = MagicMock(); diag_res.scalar_one_or_none.return_value = diag
    onb_res = MagicMock(); onb_res.scalars.return_value.first.return_value = onb
    refetch = MagicMock(); refetch.scalar_one_or_none.return_value = diag
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[diag_res, onb_res, refetch])
    db.commit = AsyncMock(); db.rollback = AsyncMock()

    with patch("app.tasks.diagnostico_tasks.generate_diagnostico", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            await _run_generation("d1", db)

    assert diag.status == "failed"
    assert diag.fail_reason == "error"
