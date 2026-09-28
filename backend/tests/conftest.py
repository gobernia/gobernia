import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _sin_almacenamiento_real(monkeypatch):
    """Las pruebas NUNCA suben archivos al bucket real (el .env local trae credenciales de prod)."""
    from unittest.mock import AsyncMock

    for mod in ("app.services.documents.storage", "app.api.v1.evidence.router",
                "app.api.v1.documents.router", "app.api.v1.onboarding.etapa7",
                "app.api.v1.board_sessions.documents"):
        try:
            monkeypatch.setattr(f"{mod}.upload_to_storage", AsyncMock(side_effect=lambda c, k: k))
        except (AttributeError, ImportError):
            pass
