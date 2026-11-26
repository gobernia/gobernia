import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _llamadas_de_la_familia_4(monkeypatch):
    """Los dobles de las pruebas de siempre imitan la llamada de la familia 4.x
    (_create_with_retry con la herramienta forzada). El camino de los modelos nuevos
    (Opus/Sonnet 5.5) se prueba aparte, en tests/unit/test_modelos.py."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "DIAGNOSTICO_AI_MODEL", "claude-opus-4-8")
    monkeypatch.setattr(settings, "AI_MODEL", "claude-sonnet-4-6")


@pytest.fixture(autouse=True)
def _sin_almacenamiento_real(monkeypatch):
    """Las pruebas NUNCA suben archivos al bucket real (el .env local trae credenciales de prod)."""
    from unittest.mock import AsyncMock

    for mod in ("app.services.documents.storage", "app.api.v1.evidence.router",
                "app.api.v1.documents.router", "app.api.v1.onboarding.etapa7",
                "app.api.v1.board_sessions.documents", "app.api.v1.colaboradores.router"):
        try:
            monkeypatch.setattr(f"{mod}.upload_to_storage", AsyncMock(side_effect=lambda c, k: k))
        except (AttributeError, ImportError):
            pass
