from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Cuando se usa el pooler de Supabase (pgBouncer en Transaction mode, puerto 6543),
# asyncpg no puede usar prepared statements — se desactivan con statement_cache_size=0.
# Con conexión directa (puerto 5432) no hace falta y se omite.
_connect_args = {"statement_cache_size": 0} if settings.USE_POOLER else {}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=not settings.is_production,
    pool_size=5,       # Supabase free tier tiene límite de conexiones
    max_overflow=10,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def task_session():
    """Sesión aislada para tasks de Celery.

    Cada task corre en su propio `asyncio.run()` (event loop nuevo) dentro de un proceso
    prefork. Reusar el `engine` global —cuyas conexiones quedan atadas al primer loop que
    las usa— provoca errores de asyncpg cuando hay tasks concurrentes o sucesivas:
    'got Future attached to a different loop' / 'cannot perform operation: another
    operation is in progress'. Aquí creamos un engine NullPool propio (sin reuso de
    conexiones), ligado al loop actual, y lo destruimos al terminar.
    """
    eng = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        connect_args=_connect_args,
    )
    maker = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    try:
        async with maker() as session:
            yield session
    finally:
        await eng.dispose()
