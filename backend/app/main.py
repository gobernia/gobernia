from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.onboarding.router import router as onboarding_router
from app.api.v1.agents.router import router as agents_router
from app.api.v1.documents.router import router as documents_router
from app.api.v1.board_sessions.router import router as board_sessions_router
from app.api.v1.action_plans.router import router as action_plans_router
from app.api.v1.annual_plan.router import router as annual_plan_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verificar conexión a DB
    from app.db.session import engine
    from sqlalchemy import text
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    # Shutdown: cerrar conexiones
    await engine.dispose()


app = FastAPI(
    title="Gobernia API",
    description="Backend del Consejo de Administración con IA",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(onboarding_router, prefix="/api/v1/onboarding", tags=["onboarding"])
app.include_router(agents_router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(documents_router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(board_sessions_router, prefix="/api/v1", tags=["board-sessions"])
app.include_router(action_plans_router, prefix="/api/v1", tags=["action-plans"])
app.include_router(annual_plan_router, prefix="/api/v1", tags=["annual-plan"])


@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok", "version": "1.0.0", "service": "gobernia-api"}
