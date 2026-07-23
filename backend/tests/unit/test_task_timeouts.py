"""
El '5hr colgado' nunca debe repetirse: el worker tiene límite de tiempo y una tarea que
se topa con él marca 'failed' SIN reintentar (reintentar solo se vuelve a colgar y re-cobra).
"""
from unittest.mock import patch

import pytest
from celery.exceptions import SoftTimeLimitExceeded

from app.tasks.worker import celery_app
from app.tasks import annual_plan_tasks, diagnostico_tasks, foda_tasks


def test_worker_tiene_limites_de_tiempo():
    c = celery_app.conf
    assert c.task_soft_time_limit and c.task_soft_time_limit <= 1800
    assert c.task_time_limit and c.task_time_limit > c.task_soft_time_limit
    assert c.worker_prefetch_multiplier == 1
    assert c.broker_connection_retry_on_startup is True


@pytest.mark.parametrize("mod, task, arg", [
    (annual_plan_tasks, "generate_annual_plan_task", "plan-id"),
    (diagnostico_tasks, "generate_diagnostico_task", "diag-id"),
    (foda_tasks, "generate_foda_task", "user-id"),
])
def test_timeout_no_reintenta(mod, task, arg):
    """SoftTimeLimitExceeded se propaga tal cual (la tarea ya marcó 'failed'); NO llama a self.retry."""
    fn = getattr(mod, task)
    entry = "_entrypoint" if hasattr(mod, "_entrypoint") else "_run"
    with patch.object(mod, entry, side_effect=SoftTimeLimitExceeded()), \
         patch.object(fn, "retry", side_effect=AssertionError("no debe reintentar en timeout")) as retry:
        with pytest.raises(SoftTimeLimitExceeded):
            fn.run(arg)
        retry.assert_not_called()
